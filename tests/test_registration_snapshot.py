"""Manual snapshots use synthetic data and a substituted delivery boundary only."""
import io
import uuid
import pytest
from openpyxl import load_workbook
from test_final_registration import harness, group
from registration_snapshot import dispatch_snapshot


def test_snapshot_sends_current_table_all_submitted_scans_and_is_idempotent(harness):
    group(harness, 2)
    group(harness, 1)
    sent=[]
    def deliver(recipient,filename,content,mime,caption):
        sent.append((recipient,filename,content,mime,caption))
        return {'message_id':len(sent),'file_id':'synthetic-file-'+str(len(sent)),'sha256':'synthetic-verified-hash'}
    request_id=str(uuid.uuid4())
    report=dispatch_snapshot(harness.service,request_id,111111111,deliver)
    assert report['passports']==3 and report['files']==4 and report['verified']==4
    assert len(sent)==4 and all(item[0]==111111111 for item in sent)
    book=load_workbook(io.BytesIO(sent[0][2])); assert book.active.max_row==4
    assert dispatch_snapshot(harness.service,request_id,111111111,deliver)['files']==4
    assert len(sent)==4
    with harness.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM final_registrations').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM final_outbox WHERE done=0').fetchone()[0]==4


def test_snapshot_rejects_nonconfigured_recipient(harness):
    with pytest.raises(ValueError):
        dispatch_snapshot(harness.service,str(uuid.uuid4()),999999999,lambda *args: None)


def test_snapshot_retry_resumes_after_completed_attachment(harness):
    group(harness, 1)
    sent=[]
    failed=[False]
    def deliver(*args):
        if len(sent)==1 and not failed[0]:
            failed[0]=True
            raise RuntimeError('synthetic delivery failure')
        sent.append(args)
        return {'message_id':len(sent),'file_id':'synthetic-file','sha256':'synthetic-hash'}
    request_id=str(uuid.uuid4())
    with pytest.raises(RuntimeError):dispatch_snapshot(harness.service,request_id,111111111,deliver)
    assert len(sent)==1
    assert dispatch_snapshot(harness.service,request_id,111111111,deliver)['files']==2
    assert len(sent)==2


def test_snapshot_expiry_removes_encrypted_manual_job(harness):
    from final_registration import RETENTION_TIMESTAMP
    group(harness)
    request_id=str(uuid.uuid4())
    dispatch_snapshot(harness.service,request_id,111111111,lambda *args: {'message_id':1,'file_id':'synthetic','sha256':'synthetic'})
    harness.service.clock=lambda:RETENTION_TIMESTAMP
    harness.service.purge_expired()
    with harness.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM final_outbox').fetchone()[0]==0


def test_snapshot_keeps_review_records_on_a_separate_sheet(harness,monkeypatch):
    from types import SimpleNamespace
    from test_review_mode import review_service
    group(harness,1)
    client,_,_=review_service(harness,monkeypatch)
    client.environ_base['HTTP_X_REGISTRATION_REVIEW']='s'*48
    group(SimpleNamespace(client=client),1)
    sent=[]
    def deliver(*args):
        sent.append(args)
        return {'message_id':len(sent),'file_id':'synthetic','sha256':'synthetic'}
    report=dispatch_snapshot(harness.service,str(uuid.uuid4()),111111111,deliver)
    book=load_workbook(io.BytesIO(sent[0][2]))
    assert book['Final registrations'].max_row==2
    assert book['Test registrations'].max_row==2
    assert report['passports']==2 and report['finalRegistrations']==1 and report['testRegistrations']==1


def test_telegram_readback_verifies_exact_document_and_destination(monkeypatch):
    from types import SimpleNamespace
    from registration_snapshot import _verified_document
    content=b'SYNTHETIC DOCUMENT BYTES'
    monkeypatch.setattr('registration_snapshot.requests.post',lambda *args,**kwargs:SimpleNamespace(status_code=200,json=lambda:{'ok':True,'result':{'message_id':7,'chat':{'id':111111111,'type':'private'},'document':{'file_id':'synthetic-file'}}}))
    def get(url,**kwargs):
        if url.endswith('/getFile'):
            return SimpleNamespace(status_code=200,json=lambda:{'ok':True,'result':{'file_path':'documents/synthetic.bin'}})
        return SimpleNamespace(status_code=200,content=content)
    monkeypatch.setattr('registration_snapshot.requests.get',get)
    receipt=_verified_document('synthetic-token',111111111,'synthetic.bin',content,'application/octet-stream','test')
    assert receipt['message_id']==7
    with pytest.raises(RuntimeError):
        _verified_document('synthetic-token',222222222,'synthetic.bin',content,'application/octet-stream','test')
    monkeypatch.setattr('registration_snapshot.requests.get',lambda url,**kwargs: get(url,**kwargs) if url.endswith('/getFile') else SimpleNamespace(status_code=200,content=b'wrong data'))
    with pytest.raises(RuntimeError):
        _verified_document('synthetic-token',111111111,'synthetic.bin',content,'application/octet-stream','test')

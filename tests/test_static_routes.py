from pathlib import Path
import importlib.util
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def load_site(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix='ceibs-static-tests-', dir='/home/hermes/.hermes/cache/scratch'))
    monkeypatch.setenv('CEIBS_DATA_DIR', str(root))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('FINAL_REGISTRATION_ENABLED', '0')
    monkeypatch.setenv('FINAL_REGISTRATION_DISABLE_WORKER', '1')
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('ceibs_site_security_test', ROOT / 'server.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_source_and_repo_files_are_not_public(monkeypatch):
    site = load_site(monkeypatch)
    with site.app.test_client() as client:
        for path in ('/server.py','/requirements.txt','/.git/config','/mail_export.py','/README.md'):
            response = client.get(path)
            assert response.status_code == 404, (path, response.status_code)


def test_expected_public_pages_and_assets_remain_accessible(monkeypatch):
    site = load_site(monkeypatch)
    with site.app.test_client() as client:
        for path in ('/','/ru.html','/zh.html','/js/main.js','/content/en.json','/programme/ru.html','/images/wechat-qr.webp','/fonts/noto-sans-latin.woff2','/fonts/noto-sans-cyrillic.woff2','/fonts/noto-serif-latin.woff2','/fonts/noto-serif-cyrillic.woff2','/favicon.svg'):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)


def test_private_data_paths_are_not_public(monkeypatch):
    site = load_site(monkeypatch)
    probe = site.DATA_DIR / 'test-private-probe.txt'
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text('TEST ONLY - private route must not serve this')
    with site.app.test_client() as client:
        for path in ('/data/test-private-probe.txt','/data/pre_registrations.sqlite','/uploads/passport.pdf','/api/passports/example'):
            assert client.get(path).status_code == 404

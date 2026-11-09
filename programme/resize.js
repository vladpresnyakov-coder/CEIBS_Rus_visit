(() => {
  const root=document.querySelector('main');
  let pending=false;
  function report(){
    if(pending)return;
    pending=true;
    requestAnimationFrame(()=>{
      pending=false;
      parent.postMessage({type:'ceibs-programme-height',height:Math.ceil(root.getBoundingClientRect().height)},location.origin);
    });
  }
  new ResizeObserver(report).observe(root);
  addEventListener('load',report);
  addEventListener('resize',report);
  document.fonts.ready.then(report);
  report();
})();
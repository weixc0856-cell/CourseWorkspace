const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=4;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const ease=t=>1-Math.pow(1-Math.max(0,Math.min(1,t)),3);
const cards=[['问','query'],['答','key'],['加权','weighted sum']];
window.seek=async t=>{
  x.fillStyle=PAPER;x.fillRect(0,0,W,H);
  x.strokeStyle='#E7DFD0';x.lineWidth=1;
  for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
  for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}
  const idx=t>=1.04?2:(t>=0.66?1:0);
  const local=idx===0?t:idx===1?(t-0.66):(t-1.04);
  const a=ease(local/0.18);
  x.save();x.globalAlpha=a;x.fillStyle=idx===2?ACCENT:INK;x.font=`700 220px ${FONT}`;x.textAlign='center';x.textBaseline='middle';
  x.fillText(cards[idx][0],W/2,500);
  x.fillStyle=MUTED;x.font=`400 44px ${FONT}`;x.fillText(cards[idx][1],W/2,700);
  x.fillStyle=MUTED;x.font=`600 24px ${FONT}`;x.textAlign='left';x.fillText(`0${idx+1} / 03`,160,130);
  x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.restore();
};
window.READY=true;

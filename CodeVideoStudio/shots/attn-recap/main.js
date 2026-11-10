const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=6;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757',GRID='#E7DFD0';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=t=>1-Math.pow(1-clamp(t),3);
const pulse=(t,at,w=0.5)=>{const d=Math.abs(t-at)/w;return d>=1?0:1-d;};
window.seek=async t=>{
  x.fillStyle=PAPER;x.fillRect(0,0,W,H);x.strokeStyle=GRID;x.lineWidth=1;
  for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
  for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}
  x.save();x.font=`600 24px ${FONT}`;x.fillStyle=MUTED;x.textAlign='left';x.fillText('06 · 收尾',160,130);
  x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.fillStyle=ACCENT;x.fillRect(W-160-190,112,18,18);x.restore();
  const intro=ease((t-0.3)/0.4)*(1-ease((t-2.9)/0.35));
  x.save();x.globalAlpha=intro;x.fillStyle=INK;x.font=`700 76px ${FONT}`;x.textAlign='center';x.fillText('下一次看到注意力',W/2,470);x.restore();
  x.save();x.globalAlpha=ease((t-3.0)/0.4);x.fillStyle=INK;x.font=`700 84px ${FONT}`;x.textAlign='center';x.fillText('先问：',W/2,420);x.restore();
  const s=1+0.05*pulse(t,4.0,0.6);
  x.save();x.translate(W/2,620);x.scale(s,s);x.globalAlpha=ease((t-3.6)/0.5);x.fillStyle=ACCENT;x.font=`700 140px ${FONT}`;x.textAlign='center';x.textBaseline='middle';x.fillText('它在问谁？',0,0);x.restore();
  const words=['The','animal',"didn't",'cross','street'];const total=760,left=W/2-total/2;let pos=left;
  words.forEach((w,i)=>{
    x.save();x.font=`600 40px ${FONT}`;const wd=x.measureText(w).width;const active=Math.floor(t*1.1)%5===i;
    x.globalAlpha=ease((t-1.6)/0.5)*(active?1:0.35);x.fillStyle=active?ACCENT:INK;x.textAlign='left';x.fillText(w,pos,790);
    if(active){x.strokeStyle=ACCENT;x.lineWidth=3;x.strokeRect(pos-12,752,wd+24,58);}x.restore();pos+=wd+40;
  });
};
window.READY=true;

const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=7;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757',TEAL='#4C7A6A',GRID='#E7DFD0';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=t=>1-Math.pow(1-clamp(t),3);
function bg(){x.fillStyle=PAPER;x.fillRect(0,0,W,H);x.strokeStyle=GRID;x.lineWidth=1;
 for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
 for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}}
function label(t){x.save();x.font=`600 24px ${FONT}`;x.fillStyle=MUTED;x.textAlign='left';x.fillText('01 · 注意力',160,130);
 x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.fillStyle=ACCENT;x.fillRect(W-160-190,112,18,18);x.restore();}
function center(text,y,size,color,alpha){if(alpha<=0)return;x.save();x.globalAlpha=alpha;x.fillStyle=color;x.font=`700 ${size}px ${FONT}`;x.textAlign='center';x.textBaseline='middle';x.fillText(text,W/2,y);x.restore();}
function tokens(t){
  const words=['The','animal',"didn't",'cross','street'];
  const total=760,left=W/2-total/2;let pos=left;
  words.forEach((w,i)=>{
    x.save();x.font=`600 40px ${FONT}`;const wd=x.measureText(w).width;
    const active=(Math.floor(t*1.2)%5)===i;
    x.globalAlpha=0.35+ease((t-0.6)/1.2)*(active?0.65:0.25);
    x.fillStyle=active?ACCENT:INK;x.textAlign='left';x.fillText(w,pos,800);
    if(active){x.strokeStyle=ACCENT;x.lineWidth=3;x.strokeRect(pos-12,762,wd+24,58);}
    x.restore();pos+=wd+40;
  });
}
window.seek=async t=>{
  bg();label(t);
  const a=ease((t-0.15)/0.35);
  const out=1-ease((t-1.8)/0.35);
  center('注意力',430,150,INK,a*out);
  center('到底在做什么？',600,86,MUTED,ease((t-0.55)/0.4)*out);
  center('让每个词',470,120,INK,ease((t-2.0)/0.4));
  center('去找它该看的地方',650,120,ACCENT,ease((t-3.3)/0.5));
  tokens(t);
};
window.READY=true;

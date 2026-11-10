const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=16;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757',TEAL='#4C7A6A',GRID='#E7DFD0';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=t=>1-Math.pow(1-clamp(t),3);
const tokens=['The','animal',"didn't",'cross','street'];
function weights(){const m=[];for(let r=0;r<5;r++){const row=[];let sum=0;
 for(let c=0;c<5;c++){const v=Math.exp(-Math.abs(r-c)*0.75)+(r===c?0.9:0)+0.08;row.push(v);sum+=v;}
 m.push(row.map(v=>v/sum));}return m;}
const M=weights();
const nodes=tokens.map((_,i)=>({x:340+i*310,y:560}));
function bg(){x.fillStyle=PAPER;x.fillRect(0,0,W,H);x.strokeStyle=GRID;x.lineWidth=1;
 for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
 for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}}
function head(){x.save();x.font=`600 24px ${FONT}`;x.fillStyle=MUTED;x.textAlign='left';x.fillText('04 · 加权',160,130);
 x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.fillStyle=ACCENT;x.fillRect(W-160-190,112,18,18);
 x.textAlign='left';x.fillStyle=INK;x.font=`700 54px ${FONT}`;x.fillText('权重让词与词交换信息',160,210);x.restore();}
function edge(a,b,w,alpha){
  const mx=(a.x+b.x)/2,my=Math.min(a.y,b.y)-90-Math.abs(a.x-b.x)*0.12;
  x.save();x.globalAlpha=alpha;x.strokeStyle=w>0.25?TEAL:ACCENT;x.lineWidth=1+14*w;x.lineCap='round';
  x.beginPath();x.moveTo(a.x,a.y);x.quadraticCurveTo(mx,my,b.x,b.y);x.stroke();
  x.restore();return {mx,my};
}
function particle(a,b,mx,my,phase,w){
  const t=phase%1,mt=1-t;
  const px=mt*mt*a.x+2*mt*t*mx+t*t*b.x;
  const py=mt*mt*a.y+2*mt*t*my+t*t*b.y;
  x.save();x.globalAlpha=0.85;x.fillStyle=TEAL;x.beginPath();x.arc(px,py,4+8*w,0,Math.PI*2);x.fill();x.restore();
}
window.seek=async t=>{
  bg();head();
  const build=ease(t/3.0);
  const settle=ease((t-9.0)/2.0);
  const wscale=0.35+0.65*build;
  for(let i=0;i<5;i++)for(let j=0;j<5;j++){
    if(i===j)continue;const w=M[i][j]*wscale;
    const weak=w<0.18;
    const alpha=(weak?0.10:0.22+0.6*w)*(weak?(1-0.75*settle):1);
    const mid=edge(nodes[i],nodes[j],w,alpha);
    if(!weak && build>0.7){for(let k=0;k<2;k++)particle(nodes[i],nodes[j],mid.mx,mid.my,t*0.35+k*0.5+i*0.13+j*0.07,w);}
  }
  for(let i=0;i<5;i++){
    const n=nodes[i];const active=Math.floor(t*0.8)%5===i;
    x.save();x.globalAlpha=1;x.fillStyle=active?ACCENT:PAPER;x.strokeStyle=active?ACCENT:INK;x.lineWidth=4;
    x.beginPath();x.arc(n.x,n.y,54,0,Math.PI*2);x.fill();x.stroke();
    x.fillStyle=active?PAPER:INK;x.font=`700 26px ${FONT}`;x.textAlign='center';x.textBaseline='middle';x.fillText(tokens[i],n.x,n.y);
    x.restore();
  }
  x.save();x.fillStyle=MUTED;x.font=`400 22px ${FONT}`;x.textAlign='left';x.textAlign='left';x.fillText('边 = 注意力权重（示意，不是 value 向量）',160,270);x.restore();
  const cap=ease((t-9.5)/0.8);
  if(cap>0){x.save();x.globalAlpha=cap;x.fillStyle=INK;x.font=`600 34px ${FONT}`;x.textAlign='center';
    x.fillText('重要的连接变粗，不重要的退到背景里',W/2,960);x.restore();}
};
window.READY=true;

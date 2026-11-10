const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=13;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757',GRID='#E7DFD0';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=t=>1-Math.pow(1-clamp(t),3);
const tokens=['The','animal',"didn't",'cross','street'];
function weights(){
  const m=[];for(let r=0;r<5;r++){const row=[];let sum=0;
    for(let c=0;c<5;c++){const v=Math.exp(-Math.abs(r-c)*0.75)+(r===c?0.9:0)+0.08;row.push(v);sum+=v;}
    m.push(row.map(v=>v/sum));}return m;}
const M=weights();
function bg(){x.fillStyle=PAPER;x.fillRect(0,0,W,H);x.strokeStyle=GRID;x.lineWidth=1;
 for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
 for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}}
function head(){x.save();x.font=`600 24px ${FONT}`;x.fillStyle=MUTED;x.textAlign='left';x.fillText('03 · 矩阵',160,130);
 x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.fillStyle=ACCENT;x.fillRect(W-160-190,112,18,18);
 x.textAlign='left';x.fillStyle=INK;x.font=`700 54px ${FONT}`;x.fillText('注意力矩阵',160,210);
 x.fillStyle=MUTED;x.font=`400 28px ${FONT}`;x.fillText('每一行，是一个词望向整句话的目光',160,258);x.restore();}
window.seek=async t=>{
  bg();head();
  const cell=88,gap=6,gridW=5*cell+4*gap,left=W/2-gridW/2+40,top=340;
  const build=ease((t-0.2)/1.4);
  const current=clamp(Math.floor((t-2.0)/1.7),0,4);
  for(let r=0;r<5;r++){
    x.save();x.font=`500 26px ${FONT}`;x.fillStyle=r===current?ACCENT:INK;x.textAlign='right';x.textBaseline='middle';
    x.globalAlpha=0.45+0.55*build;x.fillText(tokens[r],left-24,top+r*(cell+gap)+cell/2);x.restore();
  }
  for(let c=0;c<5;c++){
    x.save();x.font=`500 26px ${FONT}`;x.fillStyle=c===current?ACCENT:INK;x.textAlign='center';x.textBaseline='bottom';
    x.globalAlpha=0.45+0.55*build;x.fillText(tokens[c],left+c*(cell+gap)+cell/2,top-18);x.restore();
  }
  for(let r=0;r<5;r++){for(let cc=0;cc<5;cc++){
    const w=M[r][cc];const px=left+cc*(cell+gap),py=top+r*(cell+gap);
    const appear=ease((t-0.3-(r+cc)*0.06)/0.5);
    const focus=(r===current?1:0.35);
    x.save();x.globalAlpha=appear*(0.25+w*0.75)*focus;
    x.fillStyle=ACCENT;x.fillRect(px,py,cell,cell);
    x.globalAlpha=appear*focus;x.strokeStyle=r===current?ACCENT:GRID;x.lineWidth=r===current?4:1;
    x.strokeRect(px,py,cell,cell);
    if(r===current){x.fillStyle=INK;x.font=`600 26px ${FONT}`;x.textAlign='center';x.textBaseline='middle';x.fillText(w.toFixed(2),px+cell/2,py+cell/2);}
    x.restore();
  }}
  x.save();x.fillStyle=MUTED;x.font=`400 22px ${FONT}`;x.textAlign='left';x.fillText('数值为示意，不是模型输出',160,290);x.restore();
  const cap=ease((t-10.2)/0.6);
  if(cap>0){x.save();x.globalAlpha=cap;x.fillStyle=INK;x.font=`600 34px ${FONT}`;x.textAlign='center';
    x.fillText('每一行，都是一个词望向全句的目光',W/2,1010);x.restore();}
};
window.READY=true;

const c=document.getElementById('stage'),x=c.getContext('2d');
const W=1920,H=1080;
window.DUR=9;
const PAPER='#F6F1E7',INK='#1D1B17',MUTED='#7C756B',ACCENT='#D97757',GRID='#E7DFD0';
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=t=>1-Math.pow(1-clamp(t),3);
const tokens=['The','animal',"didn't",'cross','street'];
function w(r,c){let v=Math.exp(-Math.abs(r-c)*0.75)+(r===c?0.9:0)+0.08,s=0;
 for(let k=0;k<5;k++)s+=Math.exp(-Math.abs(r-k)*0.75)+(r===k?0.9:0)+0.08;return v/s;}
window.seek=async t=>{
  x.fillStyle=PAPER;x.fillRect(0,0,W,H);x.strokeStyle=GRID;x.lineWidth=1;
  for(let i=80;i<W;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,H);x.stroke();}
  for(let j=80;j<H;j+=80){x.beginPath();x.moveTo(0,j);x.lineTo(W,j);x.stroke();}
  x.save();x.font=`600 24px ${FONT}`;x.fillStyle=MUTED;x.textAlign='left';x.fillText('05 · 遮罩',160,130);
  x.textAlign='right';x.fillStyle=INK;x.fillText('WORKSPACE',W-160,130);x.fillStyle=ACCENT;x.fillRect(W-160-190,112,18,18);
  x.textAlign='left';x.fillStyle=INK;x.font=`700 54px ${FONT}`;x.fillText('解码器：能看当前和之前',160,210);
  x.fillStyle=MUTED;x.font=`400 28px ${FONT}`;x.fillText('不能看未来；未来位置被遮住',160,258);x.restore();
  const cell=88,gap=6,gridW=5*cell+4*gap,left=W/2-gridW/2+40,top=340;
  const build=ease((t-0.2)/1.2),mask=ease((t-1.4)/1.2);
  for(let r=0;r<5;r++){
    x.save();x.font=`500 26px ${FONT}`;x.fillStyle=INK;x.textAlign='right';x.textBaseline='middle';x.globalAlpha=0.45+0.55*build;x.fillText(tokens[r],left-24,top+r*(cell+gap)+cell/2);x.restore();
  }
  for(let cc=0;cc<5;cc++){
    x.save();x.font=`500 26px ${FONT}`;x.fillStyle=INK;x.textAlign='center';x.textBaseline='bottom';x.globalAlpha=0.45+0.55*build;x.fillText(tokens[cc],left+cc*(cell+gap)+cell/2,top-18);x.restore();
  }
  for(let r=0;r<5;r++)for(let cc=0;cc<5;cc++){
    const px=left+cc*(cell+gap),py=top+r*(cell+gap),future=cc>r;
    x.save();x.globalAlpha=build*(future?0.18:0.25+w(r,cc)*0.7);
    x.fillStyle=future?MUTED:ACCENT;x.fillRect(px,py,cell,cell);
    x.globalAlpha=build;x.strokeStyle=future?MUTED:GRID;x.lineWidth=future?2:1;x.strokeRect(px,py,cell,cell);
    if(future&&mask>0){x.globalAlpha=mask*0.9;x.strokeStyle=MUTED;x.lineWidth=2;
      for(let k=-cell;k<cell;k+=18){x.beginPath();x.moveTo(px+Math.max(0,k),py+Math.max(0,-k));x.lineTo(px+Math.min(cell,cell+k),py+Math.min(cell,cell-k));x.stroke();}
    }
    x.restore();
  }
};
window.READY=true;

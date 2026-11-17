"""Offline HTML fallback: actual saved states, causal monitoring, no web port/widget server."""
import json
from pathlib import Path
import numpy as np
from .geometry import hopper_walls


def export_html(bundle,path):
    a=bundle.arrays;m=bundle.monitoring
    data=dict(run_id=bundle.record['run_id'],time=a['time_s'].tolist(),position=a['position_m'].tolist(),
        speed=np.linalg.norm(a['velocity_m_s'],axis=2).tolist(),active=a['active'].tolist(),radius=a['radius_m'].tolist(),
        walls=[hopper_walls(bundle.config,float(t)).tolist() for t in a['time_s']],
        contacts=a['contact_graph'].tolist() if 'contact_graph' in a else None,
        counts=a['discharged_count'].tolist(),remaining=a['remaining_count'].tolist(),
        states=m.observed_state.tolist(),rule=m.rule_score.tolist(),ml=[None if x is None or not np.isfinite(x) else x for x in m.ml_score],
        rule_alert=m.rule_alert.tolist(),ml_alert=m.ml_alert.tolist(),
        occupancy=bundle.features.near_occupancy_estimate.tolist(),velocity=bundle.features.near_speed_mean_m_s.tolist(),
        flux=bundle.features.flow_rate_50ms_particles_s.tolist(),
        width=bundle.config.width_m,top=max(.06,float(a['position_m'][0,:,1].max())+.012),
        view_width=2*max(.025,min(bundle.config.width_m*.55,float(np.abs(a['position_m'][0,:,0]).max())+.010)))
    text='''<!doctype html><meta charset="utf-8"><title>PharmaFlow actual DEM replay</title>
<style>body{font:15px system-ui;background:#f5f8fa;color:#233e4b;max-width:1050px;margin:24px auto}canvas{background:white;border:1px solid #dbe4e8;border-radius:8px}button,input{margin:8px}#clock{font-size:18px}small{color:#46616b}</style>
<h2>PharmaFlow · actual 2D DEM replay</h2><small id="run"></small>
<p>Online observations only. Raw warning scores are not calibrated risk probabilities. No future onset/confirmation annotations.</p>
<button id="play">Play</button><button id="pause">Pause</button><button id="prev">Previous</button><button id="next">Next</button>
<input id="frame" type="range" min="0" value="0" style="width:48%"><label><input id="contacts" type="checkbox" checked>Near-outlet contacts</label>
<div id="clock"></div><p id="status"></p><canvas id="scene" width="1000" height="520"></canvas>
<p>Speed scale: 0 (dark blue) – 1 m/s (yellow), saturated above 1. Physical timestamps are original; playback is slowed down.</p>
<button id="png">Save screenshot</button><script>const D=__DATA__;
const $=s=>document.getElementById(s),ctx=$('scene').getContext('2d');let frame=0,timer=null;
$('frame').max=D.time.length-1;$('run').textContent=D.run_id;
function stop(){clearInterval(timer);timer=null}function seek(i){frame=Math.max(0,Math.min(D.time.length-1,i));$('frame').value=frame;draw()}
function point(p){return [20+(p[0]/D.width+.55)*350,460-(p[1]+.015)/(D.top+.015)*420]}
function line(points,color,width=1){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke()}
function plot(values,y,title,color,max=1){ctx.fillStyle='#233e4b';ctx.fillText(title,420,y-12);line([[420,y],[970,y]],'#aabcc2');const end=D.time[D.time.length-1];line(values.slice(0,frame+1).map((v,i)=>[420+550*D.time[i]/end,y-65*(v||0)/max]),color,2);}
function draw(){ctx.clearRect(0,0,1000,520);ctx.font='13px system-ui';ctx.fillStyle='#233e4b';ctx.fillText('Actual disk radius and wall geometry',20,24);
for(const w of D.walls[frame])line(w.map(point),'#233e4b',2);
const n=D.radius.length,p=D.position[frame];
if($('contacts').checked&&D.contacts){const g=D.contacts[frame];for(let i=0;i<n;i++){for(let j=i+1;j<n;j++)if(g[i][j])line([point(p[i]),point(p[j])],'#cb5539');
for(let j=0;j<2;j++)if(g[i][n+j]){const w=D.walls[frame][j],v=[w[1][0]-w[0][0],w[1][1]-w[0][1]],q=Math.max(0,Math.min(1,((p[i][0]-w[0][0])*v[0]+(p[i][1]-w[0][1])*v[1])/(v[0]*v[0]+v[1]*v[1])));line([point(p[i]),point([w[0][0]+q*v[0],w[0][1]+q*v[1]])],'#cb5539')}}}
// Canvas physical x/y scale is identical: resize vertical coordinate to match x scale.
for(let i=0;i<n;i++)if(D.active[frame][i]){const v=Math.max(0,Math.min(1,D.speed[frame][i]));ctx.fillStyle=`hsl(${245-190*v},65%,${30+30*v}%)`;ctx.beginPath();ctx.ellipse(...point(p[i]),D.radius[i]/D.width*350,D.radius[i]/(D.top+.015)*420,0,0,2*Math.PI);ctx.fill();ctx.strokeStyle='#233e4b';ctx.stroke()}
plot(D.counts,130,'Discharged particles','#277c9e',n);plot(D.flux,230,'Trailing 50ms flow [particles/s]','#6e98ab',Math.max(100,...D.flux.slice(0,frame+1)));
plot(D.rule,345,'Frozen M4A rule score','#bb741c');plot(D.ml,345,'','#7856a3');
for(const [k,c] of [['rule_alert','#bb741c'],['ml_alert','#7856a3']])for(let i=0;i<=frame;i++)if(D[k][i]){ctx.fillStyle=c;ctx.fillRect(418+550*D.time[i]/D.time.at(-1),350,4,7)}
ctx.fillStyle='#233e4b';ctx.fillText(`Near occupancy estimator: ${D.occupancy[frame].toFixed(3)} | local speed ${D.velocity[frame].toFixed(4)} m/s`,420,410);ctx.fillText('Physical time [s]: 0 to '+D.time.at(-1).toFixed(3),420,450);
$('clock').textContent=`t = ${D.time[frame].toFixed(3)} s | frame ${frame} | discharged ${D.counts[frame]} | remaining ${D.remaining[frame]}`;
$('status').textContent=D.states[frame].replaceAll('_',' ')+` | rule ${D.rule[frame].toFixed(3)} | ML ${D.ml[frame]===null?'unavailable':D.ml[frame].toFixed(3)}`;}
$('play').onclick=()=>{stop();timer=setInterval(()=>{if(frame>=D.time.length-1)stop();else seek(frame+2)},100)};
$('pause').onclick=stop;$('prev').onclick=()=>{stop();seek(frame-1)};$('next').onclick=()=>{stop();seek(frame+1)};
$('frame').oninput=()=>{stop();seek(+$('frame').value)};$('contacts').onchange=draw;
$('png').onclick=()=>{const a=document.createElement('a');a.download=D.run_id+'_frame'+frame+'.png';a.href=$('scene').toDataURL();a.click()};draw();</script>'''
    # Equal physical scale in both axes, based on the known initial-fill camera.
    text=text.replace("function point(p)","const SCALE=Math.min(350/D.view_width,420/(D.top+.015));function point(p)")
    text=text.replace("20+(p[0]/D.width+.55)*350,460-(p[1]+.015)/(D.top+.015)*420","195+p[0]*SCALE,460-(p[1]+.015)*SCALE")
    text=text.replace("D.radius[i]/D.width*350,D.radius[i]/(D.top+.015)*420","D.radius[i]*SCALE,D.radius[i]*SCALE")
    text=text.replace("for(const w of D.walls[frame])","ctx.save();ctx.beginPath();ctx.rect(10,40,370,440);ctx.clip();for(const w of D.walls[frame])")
    text=text.replace("plot(D.counts,130","ctx.restore();plot(D.counts,130")
    text=text.replace('__DATA__',json.dumps(data,allow_nan=False,separators=(',',':')).replace('</','<\\/'))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    return path


def notebook_replay(bundle):
    """Return a self-contained iframe; no ipywidgets, Streamlit proxy, or CDN required."""
    import html
    import tempfile
    from IPython.display import HTML
    with tempfile.TemporaryDirectory() as folder:
        text=export_html(bundle,Path(folder)/'replay.html').read_text(encoding='utf-8')
    return HTML('<iframe style="width:100%;height:850px;border:0" srcdoc="'+html.escape(text,quote=True)+'"></iframe>')

"""Project-native browser workbench with the public MuScriptor result controls."""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import quote

_COLORS = (
    "#1976d2",
    "#008b8b",
    "#3f8f3f",
    "#7559a6",
    "#b77900",
    "#b54f7d",
    "#087f8c",
    "#6d9628",
)


def track_file_url(path: str | Path) -> str:
    return "/file=" + quote(str(Path(path).resolve()))


def _result_instrument_label(instrument: str, language: str) -> str:
    del language
    return instrument.replace("_", " ")


def build_muscriptor_result_html(
    state: Mapping[str, object],
    translate: Callable[[str], str],
    language: str,
) -> str:
    detected = [str(item) for item in state.get("detected_instruments", [])]
    selected = [str(item) for item in state.get("selected_instruments", [])]
    ordered = list(selected or detected)
    for instrument in detected:
        if instrument not in ordered:
            ordered.append(instrument)
    instrument_metadata = state.get("instrument_metadata", {})
    if not isinstance(instrument_metadata, Mapping):
        instrument_metadata = {}
    instruments = [
        {
            "id": instrument,
            "label": _result_instrument_label(instrument, language),
            "detected": instrument in detected,
            "color": _COLORS[index % len(_COLORS)],
            "midi": instrument_metadata.get(instrument, []),
        }
        for index, instrument in enumerate(ordered)
    ]
    manifest = {
        "notes": list(state.get("notes", [])),
        "duration": float(state.get("duration", 0.0)),
        "bpm": float(state.get("bpm", 120.0)),
        "backendLabel": str(state.get("backend_label", "")),
        "sourceTrackName": str(state.get("source_track_name", "")),
        "instruments": instruments,
        "downloads": {
            "midi": str(
                state.get("midi_url")
                or track_file_url(str(state["midi_path"]))
            ),
        },
        "fileId": str(state.get("file_id", "")),
        "strings": {
            key: translate(f"muscriptor_result.{key}")
            for key in (
                "play",
                "pause",
                "follow",
                "original",
                "instruments",
                "not_detected",
                "solo",
                "mute",
                "ready",
                "linked_source",
                "zoom_help",
            )
        },
    }
    encoded = html.escape(json.dumps(manifest, ensure_ascii=False), quote=False)
    return (
        '<div class="msr-root">'
        f'<pre class="msr-manifest" hidden>{encoded}</pre>'
        '<div class="msr-host"></div>'
        "</div>"
    )


MUSCRIPTOR_RESULT_CSS = r"""
html, body { height:100%; }
html body { padding:0; background:#fff; }
body .share-shell { max-width:1600px; height:100%; min-height:0; display:flex; flex-direction:column; }
body .muscriptor-instrument-selector {
  background:#fff; border:1px solid #d5dce3;
  border-radius:6px; padding:12px 14px; box-shadow:none;
}
body .muscriptor-instrument-selector label > span:first-child {
  color:#0069aa; font-size:13px; font-weight:700;
}
body .muscriptor-instrument-selector .info {
  color:#555; font-size:12px; line-height:1.4;
}
body .muscriptor-instrument-selector [data-testid="token"] {
  background:#edf6fc; border:1px solid #b7d8ee;
  border-radius:4px; color:#24445b; font-size:12px;
}
body .muscriptor-instrument-selector input {
  color:#222; background:#fff; font-size:12px; min-height:34px;
}
.msr-root, .msr-host { min-height:0; background:#fff; }
.msr-root { flex:1 1 auto; margin:6px 3px; color:#222; font-family:Arial,Helvetica,'Noto Sans TC',sans-serif; }
.msr-host { height:100%; display:flex; flex-direction:column; }
.msr-source { color:#0069aa; font-weight:600; background:#fff; border:1px solid #d5dce3; border-radius:6px; padding:9px 12px; margin-bottom:10px; }
.msr-toolbar { flex:0 0 auto; display:flex; flex-wrap:wrap; align-items:center; gap:9px; }
.msr-btn { box-sizing:border-box; background:#fff; color:#0069aa; border:1px solid #1683bd; border-radius:4px; padding:6px 11px; cursor:pointer; box-shadow:none; font:inherit; line-height:1.25; }
.msr-btn:hover { background:#edf7fc; border-color:#0069aa; color:#00527f; }
.msr-btn:active { background:#dcedf7; }
.msr-btn:disabled { opacity:.4; cursor:default; }
.msr-btn.active { color:#fff; border-color:#0069aa; background:#0069aa; box-shadow:none; }
.msr-toolbar > .msr-btn:first-child { color:#fff; border-color:#0069aa; background:#0069aa; }
.msr-toolbar > .msr-btn:first-child:hover { border-color:#00527f; background:#005f91; }
.msr-delay { display:flex; align-items:center; gap:5px; color:#333; white-space:nowrap; }
.msr-delay input { width:62px; height:32px; box-sizing:border-box; color:#234; border:1px solid #b9c4cc; border-radius:4px; background:#fff; padding:4px 7px; }
.msr-delay input:focus { outline:2px solid rgba(0,105,170,.18); border-color:#1683bd; }
.msr-clock { font-family:monospace; color:#334; border:1px solid #d5dce3; border-radius:4px; background:#f7f9fa; padding:6px 9px; }
.msr-status { margin-left:auto; max-width:420px; min-width:0; overflow:hidden; color:#4b5963; font-size:12px; line-height:32px; text-align:right; text-overflow:ellipsis; white-space:nowrap; }
.msr-audio { position:absolute; width:1px; height:1px; opacity:.01; pointer-events:none; }
.msr-grid { flex:1 1 auto; min-height:0; display:grid; grid-template-columns:minmax(0,1fr) minmax(300px,340px); gap:12px; margin-top:6px; }
.msr-roll-scroll { height:100%; min-height:0; overflow:auto; border:1px solid #8ba5bf; border-radius:3px; background:#fff; scrollbar-color:#9aafc2 #edf2f6; scrollbar-width:thin; }
.msr-roll-scroll::-webkit-scrollbar { width:12px; height:12px; }
.msr-roll-scroll::-webkit-scrollbar-track { background:#edf2f6; border-radius:3px; }
.msr-roll-scroll::-webkit-scrollbar-thumb { background:#9aafc2; border-radius:3px; border:2px solid #edf2f6; }
.msr-roll-scroll::-webkit-scrollbar-thumb:hover { background:#7895ae; }
.msr-roll-world { position:relative; }
.msr-roll-viewport { position:sticky; left:0; overflow:hidden; }
.msr-roll { display:block; cursor:crosshair; }
.msr-playhead { position:absolute; top:0; bottom:0; width:1px; background:#f00000; pointer-events:none; will-change:transform; }
.msr-instruments { border:1px solid #d5dce3; border-radius:6px; background:#fff; padding:12px; align-self:start; box-shadow:none; }
.msr-instruments h3 { margin:0 0 9px; color:#243746; font-size:15px; font-weight:600; }
.msr-row { display:flex; align-items:center; gap:8px; min-height:32px; padding:6px 2px; border-top:1px solid #e6eaed; }
.msr-row:first-of-type { border-top:0; }
.msr-row.undetected { opacity:.38; text-decoration:line-through; }
.msr-swatch { flex:0 0 11px; width:11px; height:11px; border:1px solid rgba(0,0,0,.22); }
.msr-instrument-info { flex:1 1 auto; min-width:0; }
.msr-name { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:Arial,Helvetica,'Noto Sans TC',sans-serif; font-size:14px; line-height:1.35; color:#243746; }
.msr-meta { margin-top:2px; color:#6a7780; font-family:Arial,Helvetica,'Noto Sans TC',sans-serif; font-size:12px; line-height:1.3; }
.msr-row .msr-btn { flex:0 0 auto; min-width:30px; padding:4px 7px; text-align:center; }
.msr-row.muted .msr-name { opacity:.2; }
@media (max-width:760px) { .msr-grid { grid-template-columns:1fr; } }
"""


MUSCRIPTOR_RESULT_JS = r"""
(function () {
  "use strict";
  var sessions = [], nextSessionId = 1;
  var LEFT = 72, ROW = 11, HEADER = 18, PITCH_MIN = 0, PITCH_MAX = 127, HEIGHT = HEADER+(PITCH_MAX-PITCH_MIN+1)*ROW, MIN_PPS = 46, MAX_PPS = 368, ZOOM_STEP = 1.15, BLACK_PITCHES = new Set([1,3,6,8,10]);
  var TRACK_COLORS = ["#1976d2","#008b8b","#3f8f3f","#7559a6","#b77900","#b54f7d","#087f8c","#6d9628"];
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function el(tag, cls, text) { var n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
  function button(text, title) { var n=el("button","msr-btn",text); n.type="button"; if(title)n.title=title; return n; }
  function post(url, payload) {
    return fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload||{})})
      .then(function(r){return r.json().catch(function(){return {};}).then(function(v){if(!r.ok)throw new Error(v.error||("HTTP "+r.status));return v;});});
  }
  function ResultSession(root) {
    this.root=root; this.host=root.querySelector(".msr-host"); this.m={};
    this.position=0; this.playing=false; this.muted=new Set(); this.solo=null; this.follow=true; this.raf=0;
    this.synth="yamaha-syxg2006le";this.waitingForAudio=false;this.audioMarkerMs=null;this.audioStartPosition=0;this.audioTargetTime=null;this.audioPlaybackOrigin=0;this.audio=null;this.hls=null;this.gateCleanup=null;this.playbackGeneration=0;this.mixPromise=Promise.resolve();
    this.visualDelay=.2;try{var savedVisualDelay=localStorage.getItem("yamahaVisualDelaySeconds");if(savedVisualDelay!==null)this.visualDelay=clamp(parseFloat(savedVisualDelay)||0,0,30);}catch(e){}
    this.bpm=120;this.firstBeatDelay=0;this.gridStorageKey="";
    this.pps=92; this.drawRaf=0; this.noteIndex=[]; this.maxNoteDuration=0; this.instrumentColors={}; this.backgroundCanvas=null; this.viewportWidth=950; this.maxScroll=0; this.disposed=false; this.ownerId="midi-result-"+(nextSessionId++);
    this.onExternalPlayback=this.handleExternalPlayback.bind(this);
  }
  ResultSession.prototype.init=function(){
    try { this.m=JSON.parse(this.root.querySelector(".msr-manifest").textContent); } catch(e){this.host.textContent=String(e);return;}
    var manifestBpm=parseFloat(this.m.bpm);if(Number.isFinite(manifestBpm))this.bpm=clamp(manifestBpm,20,300);
    this.gridStorageKey="midiGrid:"+this.m.downloads.midi;try{var savedGrid=JSON.parse(localStorage.getItem(this.gridStorageKey)||"null");if(savedGrid){var savedBpm=parseFloat(savedGrid.bpm),savedFirstBeat=parseFloat(savedGrid.firstBeatDelay);if(Number.isFinite(savedBpm))this.bpm=clamp(savedBpm,20,300);if(Number.isFinite(savedFirstBeat))this.firstBeatDelay=clamp(savedFirstBeat,-60,60);}}catch(e){}
    this.noteIndex=this.m.notes.slice().sort(function(a,b){return a.start-b.start;});
    this.maxNoteDuration=this.noteIndex.reduce(function(value,n){return Math.max(value,n.end-n.start);},0);
    var self=this;this.m.instruments.forEach(function(i,index){i.color=TRACK_COLORS[index%TRACK_COLORS.length];self.instrumentColors[i.id]=i.color;});
    this.build(); this.attachSynthAudio(); window.addEventListener("music-to-midi-playback-start",this.onExternalPlayback);
    this.play.disabled=false; this.status.textContent=this.synthLabel()+" ready"; this.drawStatic(); this.layoutPlayhead();
  };
  ResultSession.prototype.build=function(){
    var self=this,s=this.m.strings;
    if(this.m.sourceTrackName){this.host.appendChild(el("div","msr-source",s.linked_source.replace("{track}",this.m.sourceTrackName).replace("{backend}",this.m.backendLabel)));}
    var bar=el("div","msr-toolbar"); this.play=button(s.play);this.play.disabled=true;this.play.onclick=function(){self.toggle();};bar.appendChild(this.play);
    var bpm=el("label","msr-delay","BPM");this.bpmInput=el("input");this.bpmInput.type="number";this.bpmInput.min="20";this.bpmInput.max="300";this.bpmInput.step=".1";this.bpmInput.value=String(this.bpm);this.bpmInput.setAttribute("aria-label","BPM");this.bpmInput.oninput=function(){var value=parseFloat(this.value);if(!Number.isFinite(value))return;self.bpm=clamp(value,20,300);self.saveGridSettings();self.scheduleDraw();};bpm.appendChild(this.bpmInput);bar.appendChild(bpm);
    var firstBeat=el("label","msr-delay","第一拍");this.firstBeatInput=el("input");this.firstBeatInput.type="number";this.firstBeatInput.min="-60";this.firstBeatInput.max="60";this.firstBeatInput.step=".01";this.firstBeatInput.value=String(this.firstBeatDelay);this.firstBeatInput.setAttribute("aria-label","第一拍延遲秒數");this.firstBeatInput.oninput=function(){var value=parseFloat(this.value);if(!Number.isFinite(value))return;self.firstBeatDelay=clamp(value,-60,60);self.saveGridSettings();self.scheduleDraw();};firstBeat.appendChild(this.bpmInput);firstBeat.appendChild(document.createTextNode("秒"));bar.appendChild(firstBeat);
    var delay=el("label","msr-delay","畫面延遲");this.delayInput=el("input");this.delayInput.type="number";this.delayInput.min="0";this.delayInput.max="30";this.delayInput.step=".1";this.delayInput.value=String(this.visualDelay);this.delayInput.setAttribute("aria-label","畫面延遲秒數");this.delayInput.oninput=function(){var value=parseFloat(this.value);if(!Number.isFinite(value))return;self.visualDelay=clamp(value,0,30);try{localStorage.setItem("yamahaVisualDelaySeconds",String(self.visualDelay));}catch(e){}};delay.appendChild(this.delayInput);delay.appendChild(document.createTextNode("秒"));bar.appendChild(delay);
    var follow=button(s.follow);follow.classList.add("active");follow.onclick=function(){self.follow=!self.follow;follow.classList.toggle("active",self.follow);};bar.appendChild(follow);
    this.clock=el("span","msr-clock","0.0s");bar.appendChild(this.clock);this.status=el("span","msr-status","");bar.appendChild(this.status);
    this.host.appendChild(bar);
    var grid=el("div","msr-grid"),scroll=el("div","msr-roll-scroll"),world=el("div","msr-roll-world"),viewport=el("div","msr-roll-viewport");
    this.canvas=el("canvas","msr-roll");this.playhead=el("div","msr-playhead");viewport.appendChild(this.canvas);viewport.appendChild(this.playhead);world.appendChild(viewport);scroll.appendChild(world);this.scroll=scroll;this.world=world;this.viewport=viewport;this.canvas.onclick=function(e){var r=self.canvas.getBoundingClientRect();self.seek((self.scroll.scrollLeft+e.clientX-r.left-LEFT)/self.pps);};
    scroll.addEventListener("scroll",function(){self.scheduleDraw();self.layoutPlayhead();},{passive:true});
    scroll.addEventListener("wheel",function(e){self.onWheel(e);},{passive:false});
    scroll.title=s.zoom_help;grid.appendChild(scroll);
    var aside=el("aside","msr-instruments");aside.appendChild(el("h3","",s.instruments));this.m.instruments.forEach(function(i,index){var row=el("div","msr-row"+(i.detected?"":" undetected"));row.dataset.instrument=i.id;row.title=i.id;var sw=el("span","msr-swatch");sw.style.background=i.detected?i.color:"#4b5157";row.appendChild(sw);var info=el("div","msr-instrument-info"),name=el("span","msr-name",i.label);name.title=i.id;info.appendChild(name);var midi=(i.midi||[]).map(function(item){var channel=Number(item.channel)+1;if(channel===10)return "Ch 10 · Drum Kit";return "Ch "+channel+" · Program "+(Number(item.program)+1)+" "+item.program_name;}).join(" | ");if(midi)info.appendChild(el("div","msr-meta",midi));row.appendChild(info);if(!i.detected){row.appendChild(el("small","",s.not_detected));}else{var solo=button("S",s.solo),mute=button("M",s.mute);solo.onclick=function(){self.toggleSolo(i.id);};mute.onclick=function(){self.toggleMute(i.id);};row.appendChild(solo);row.appendChild(mute);i.row=row;i.soloButton=solo;i.muteButton=mute;}aside.appendChild(row);});grid.appendChild(aside);this.host.appendChild(grid);
    this.resizeObserver=new ResizeObserver(function(){self.layout();});this.resizeObserver.observe(scroll);this.layout();
  };
  ResultSession.prototype.saveGridSettings=function(){try{localStorage.setItem(this.gridStorageKey,JSON.stringify({bpm:this.bpm,firstBeatDelay:this.firstBeatDelay}));}catch(e){}};
  ResultSession.prototype.synthLabel=function(){return "Yamaha S-YXG2006LE";};
  ResultSession.prototype.attachSynthAudio=function(){
    this.audio=el("audio","msr-audio");this.audio.preload="auto";this.host.appendChild(this.audio);
    var source="/stream/stream.m3u8",self=this;
    if(window.Hls&&window.Hls.isSupported()){this.hls=new window.Hls({liveSyncDurationCount:2,maxLiveSyncPlaybackRate:1,maxBufferLength:4,maxMaxBufferLength:8,backBufferLength:10});this.hls.loadSource(source);this.hls.attachMedia(this.audio);this.hls.on(window.Hls.Events.ERROR,function(_,data){if(data.fatal&&!self.disposed)self.status.textContent="Synth stream: "+data.details;});}
    else if(this.audio.canPlayType("application/vnd.apple.mpegurl"))this.audio.src=source;
    else this.status.textContent="HLS playback is unavailable";
  };
  ResultSession.prototype.start=function(){
    var self=this,generation=++this.playbackGeneration;if(this.position>=this.m.duration)this.position=0;this.audioStartPosition=this.position;this.playing=true;this.waitingForAudio=true;this.play.textContent=this.m.strings.pause;window.dispatchEvent(new CustomEvent("music-to-midi-playback-start",{detail:{owner:this.ownerId,synth:true}}));this.status.textContent="Waiting for "+this.synthLabel()+" audio…";if(this.audio)this.audio.play().catch(function(){});
    return post("/api/synth/play",{file_id:this.m.fileId,synth:this.synth,start_seconds:this.position}).then(function(state){if(self.disposed||generation!==self.playbackGeneration)return;if(self.audio)self.audio.pause();self.audioMarkerMs=state.audio_start_epoch_ms;self.audioTargetTime=null;self.syncSynthMix().catch(function(){});self.armAudioGate(generation);}).catch(function(e){if(generation!==self.playbackGeneration)return;self.playing=false;self.waitingForAudio=false;self.play.textContent=self.m.strings.play;self.status.textContent=String(e);});
  };
  ResultSession.prototype.clearAudioGate=function(){if(this.gateCleanup){this.gateCleanup();this.gateCleanup=null;}};
  ResultSession.prototype.armAudioGate=function(generation){var self=this;this.clearAudioGate();function check(){if(generation===self.playbackGeneration)self.waitForAudioFragment(generation);}if(this.hls){this.hls.on(window.Hls.Events.LEVEL_UPDATED,check);this.hls.on(window.Hls.Events.FRAG_BUFFERED,check);}if(this.audio)this.audio.addEventListener("progress",check);this.gateCleanup=function(){if(self.hls){self.hls.off(window.Hls.Events.LEVEL_UPDATED,check);self.hls.off(window.Hls.Events.FRAG_BUFFERED,check);}if(self.audio)self.audio.removeEventListener("progress",check);};check();};
  ResultSession.prototype.waitForAudioFragment=function(generation){if(generation!==this.playbackGeneration||!this.playing||!this.waitingForAudio||this.disposed)return;var levels=this.hls&&this.hls.levels||[],target=this.audioTargetTime;for(var i=0;i<levels.length&&target===null;i++){var fragments=levels[i].details&&levels[i].details.fragments||[];for(var j=0;j<fragments.length;j++){var fragment=fragments[j],rawDate=fragment.programDateTime,dateMs=rawDate instanceof Date?rawDate.getTime():Number(rawDate);if(Number.isFinite(dateMs)&&this.audioMarkerMs>=dateMs&&this.audioMarkerMs<dateMs+fragment.duration*1000){target=fragment.start+(this.audioMarkerMs-dateMs)/1000;this.audioTargetTime=target;if(this.audio)this.audio.currentTime=target;break;}}}var buffered=false;if(target!==null&&this.audio){for(var k=0;k<this.audio.buffered.length;k++){if(this.audio.buffered.start(k)<=target&&this.audio.buffered.end(k)>=target+1){buffered=true;break;}}}if(!buffered)return;this.clearAudioGate();this.audio.currentTime=target;var self=this;this.audio.play().then(function(){if(generation===self.playbackGeneration)self.waitForSynthAudio(generation);}).catch(function(e){if(generation===self.playbackGeneration)self.status.textContent="Synth audio blocked: "+e.message;});};
  ResultSession.prototype.waitForSynthAudio=function(generation){if(generation!==this.playbackGeneration||!this.playing||!this.waitingForAudio||this.disposed)return;var playingDate=this.hls&&this.hls.playingDate;if(playingDate&&playingDate.getTime()>=this.audioMarkerMs){this.waitingForAudio=false;this.audioPlaybackOrigin=this.audio.currentTime;this.status.textContent=this.synthLabel()+" playing";this.tick();return;}var self=this;this.raf=requestAnimationFrame(function(){self.waitForSynthAudio(generation);});};
  ResultSession.prototype.pause=function(stopServer){if(stopServer===undefined)stopServer=true;++this.playbackGeneration;this.clearAudioGate();var wasPlaying=this.playing;this.playing=false;this.waitingForAudio=false;this.audioMarkerMs=null;this.audioTargetTime=null;if(this.audio)this.audio.pause();this.play.textContent=this.m.strings.play;cancelAnimationFrame(this.raf);this.layoutPlayhead();return wasPlaying&&stopServer?post("/api/synth/stop",{}).catch(function(){}):Promise.resolve();};
  ResultSession.prototype.toggle=function(){if(this.playing)this.pause();else this.start();};
  ResultSession.prototype.seek=function(seconds){var self=this,was=this.playing,target=clamp(seconds,0,this.m.duration);if(!was){this.position=target;this.layoutPlayhead();return;}var stopped=this.pause(),generation=this.playbackGeneration;stopped.then(function(){if(generation!==self.playbackGeneration)return;self.position=target;self.start();});};
  ResultSession.prototype.handleExternalPlayback=function(e){if(e.detail&&e.detail.owner!==this.ownerId)this.pause(!e.detail.synth);};
  ResultSession.prototype.audible=function(id){return !this.muted.has(id);};
  ResultSession.prototype.syncSynthMix=function(){var self=this;this.mixPromise=this.mixPromise.catch(function(){}).then(function(){return post("/api/synth/mix",{solo:self.solo,muted_tracks:Array.from(self.muted)});});return this.mixPromise;};
  ResultSession.prototype.toggleMute=function(id){this.solo=null;if(this.muted.has(id))this.muted.delete(id);else this.muted.add(id);this.syncRows();this.syncSynthMix().catch(function(){});};
  ResultSession.prototype.toggleSolo=function(id){if(this.solo===id){this.solo=null;this.muted.clear();}else{this.solo=id;this.muted=new Set(this.m.instruments.filter(function(i){return i.detected&&i.id!==id;}).map(function(i){return i.id;}));}this.syncRows();this.syncSynthMix().catch(function(){});};
  ResultSession.prototype.syncRows=function(){var self=this;this.m.instruments.forEach(function(i){if(!i.detected)return;var muted=self.muted.has(i.id);i.row.classList.toggle("muted",muted);i.soloButton.classList.toggle("active",self.solo===i.id);i.muteButton.classList.toggle("active",muted);i.muteButton.textContent="M";});this.drawStatic();};
  ResultSession.prototype.tick=function(){if(!this.playing)return;this.position=Math.min(this.m.duration,this.audioStartPosition+Math.max(0,this.audio.currentTime-this.audioPlaybackOrigin-this.visualDelay));if(this.position>=this.m.duration){this.position=this.m.duration;this.pause();return;}if(this.follow){var target=LEFT+this.position*this.pps-this.viewportWidth/2;this.scroll.scrollLeft=clamp(target,0,this.maxScroll);}this.layoutPlayhead();var self=this;this.raf=requestAnimationFrame(function(){self.tick();});};
  ResultSession.prototype.layout=function(){var width=Math.max(320,this.scroll.clientWidth||950),dpr=Math.min(2,window.devicePixelRatio||1),worldWidth=Math.max(width,LEFT+this.m.duration*this.pps+80);this.viewportWidth=width;this.maxScroll=Math.max(0,worldWidth-width);this.viewport.style.width=width+"px";this.viewport.style.height=HEIGHT+"px";this.world.style.width=worldWidth+"px";this.world.style.height=HEIGHT+"px";this.canvas.style.width=width+"px";this.canvas.style.height=HEIGHT+"px";this.canvas.width=Math.round(width*dpr);this.canvas.height=Math.round(HEIGHT*dpr);this.dpr=dpr;this.rebuildBackground();this.drawStatic();this.layoutPlayhead();if(!this.verticalPositionInitialized){this.verticalPositionInitialized=true;var pitches=this.noteIndex.map(function(note){return note.pitch;}).filter(function(pitch){return pitch>=PITCH_MIN&&pitch<=PITCH_MAX;}).sort(function(a,b){return a-b;});var focusPitch=pitches.length?pitches[Math.floor(pitches.length/2)]:60,focusY=HEADER+(PITCH_MAX-focusPitch+.5)*ROW;this.scroll.scrollTop=Math.max(0,focusY-this.scroll.clientHeight/2);}};
  ResultSession.prototype.scheduleDraw=function(){var self=this;if(this.drawRaf)return;this.drawRaf=requestAnimationFrame(function(){self.drawRaf=0;self.drawStatic();});};
  ResultSession.prototype.findNoteStart=function(time){var notes=this.noteIndex,lo=0,hi=notes.length;while(lo<hi){var mid=(lo+hi)>>1;if(notes[mid].start<time)lo=mid+1;else hi=mid;}return lo;};
  ResultSession.prototype.rebuildBackground=function(){var background=document.createElement("canvas"),d=this.dpr||1,w=this.canvas.width/d;background.width=this.canvas.width;background.height=this.canvas.height;var p=background.getContext("2d");p.setTransform(d,0,0,d,0,0);p.fillStyle="#fff";p.fillRect(0,0,w,HEIGHT);p.fillStyle="#e7e7e7";p.fillRect(0,0,LEFT,HEADER);p.fillStyle="#f4f4f4";p.fillRect(LEFT,0,w-LEFT,HEADER);var blackKey=p.createLinearGradient(0,0,50,0);blackKey.addColorStop(0,"#202020");blackKey.addColorStop(.72,"#5d5d5d");blackKey.addColorStop(1,"#1b1b1b");p.beginPath();for(var pitch=PITCH_MIN;pitch<=PITCH_MAX;pitch++){var y=HEADER+(PITCH_MAX-pitch)*ROW,black=BLACK_PITCHES.has(pitch%12);p.fillStyle=black?"#edf5ff":"#fff";p.fillRect(LEFT,y,w-LEFT,ROW);p.fillStyle="#fff";p.fillRect(0,y,LEFT,ROW);if(black){p.fillStyle=blackKey;p.fillRect(0,y,50,ROW-1);p.fillStyle="rgba(255,255,255,.24)";p.fillRect(1,y+1,46,1);}p.moveTo(LEFT,y+.5);p.lineTo(w,y+.5);if(pitch%12===0){p.fillStyle="#333";p.font="9px 'MS UI Gothic',monospace";p.fillText("C"+(Math.floor(pitch/12)-1),LEFT-20,y+9);}}p.strokeStyle="#bfd2eb";p.lineWidth=1;p.stroke();p.beginPath();for(var keyPitch=PITCH_MIN;keyPitch<=PITCH_MAX;keyPitch++){var keyY=HEADER+(PITCH_MAX-keyPitch)*ROW+.5;p.moveTo(0,keyY);p.lineTo(LEFT,keyY);}p.strokeStyle="#7a7a7a";p.stroke();p.beginPath();for(var octavePitch=0;octavePitch<=PITCH_MAX;octavePitch+=12){var octaveY=HEADER+(PITCH_MAX-octavePitch)*ROW+.5;p.moveTo(LEFT,octaveY);p.lineTo(w,octaveY);}p.strokeStyle="#404040";p.stroke();p.beginPath();p.moveTo(0,HEADER-.5);p.lineTo(w,HEADER-.5);p.moveTo(LEFT-.5,0);p.lineTo(LEFT-.5,HEIGHT);p.strokeStyle="#606060";p.stroke();this.backgroundCanvas=background;};
  ResultSession.prototype.onWheel=function(e){var modifier=e.ctrlKey||e.altKey;if(modifier){e.preventDefault();var rect=this.scroll.getBoundingClientRect(),anchorX=clamp(e.clientX-rect.left,0,this.viewportWidth),anchorTime=(this.scroll.scrollLeft+anchorX-LEFT)/this.pps,factor=e.deltaY<0?ZOOM_STEP:1/ZOOM_STEP;this.pps=clamp(this.pps*factor,MIN_PPS,MAX_PPS);var worldWidth=Math.max(this.viewportWidth,LEFT+this.m.duration*this.pps+80);this.world.style.width=worldWidth+"px";this.maxScroll=Math.max(0,worldWidth-this.viewportWidth);this.scroll.scrollLeft=Math.max(0,LEFT+anchorTime*this.pps-anchorX);this.drawStatic();this.layoutPlayhead();return;}if(e.shiftKey){e.preventDefault();this.scroll.scrollLeft+=e.deltaY||e.deltaX;}};
  ResultSession.prototype.drawStatic=function(){if(!this.canvas||!this.backgroundCanvas)return;var p=this.canvas.getContext("2d"),d=this.dpr||1,w=this.canvas.width/d,h=HEIGHT,scrollX=this.scroll.scrollLeft,start=Math.max(0,(scrollX-LEFT)/this.pps),end=Math.min(this.m.duration,(scrollX+w-LEFT)/this.pps);p.setTransform(1,0,0,1,0,0);p.drawImage(this.backgroundCanvas,0,0);p.setTransform(d,0,0,d,0,0);p.save();p.beginPath();p.rect(LEFT,0,w-LEFT,h);p.clip();var beatSeconds=60/this.bpm,subdivision=beatSeconds/4,firstSubdivision=Math.floor((start-this.firstBeatDelay)/subdivision),lastSubdivision=Math.ceil((end-this.firstBeatDelay)/subdivision);p.beginPath();for(var subdivisionIndex=firstSubdivision;subdivisionIndex<=lastSubdivision;subdivisionIndex++){if(((subdivisionIndex%4)+4)%4===0)continue;var subdivisionTime=this.firstBeatDelay+subdivisionIndex*subdivision,subdivisionX=Math.round(LEFT+subdivisionTime*this.pps-scrollX)+.5;p.moveTo(subdivisionX,HEADER);p.lineTo(subdivisionX,h);}p.strokeStyle="#b8cce8";p.lineWidth=1;p.setLineDash([1,3]);p.stroke();p.setLineDash([]);var firstBeatIndex=Math.floor((start-this.firstBeatDelay)/beatSeconds),lastBeatIndex=Math.ceil((end-this.firstBeatDelay)/beatSeconds);p.beginPath();for(var beatIndex=firstBeatIndex;beatIndex<=lastBeatIndex;beatIndex++){if(((beatIndex%4)+4)%4===0)continue;var beatTime=this.firstBeatDelay+beatIndex*beatSeconds,beatX=Math.round(LEFT+beatTime*this.pps-scrollX)+.5;p.moveTo(beatX,HEADER);p.lineTo(beatX,h);}p.strokeStyle="#94b7e8";p.stroke();p.beginPath();for(var measureBeat=firstBeatIndex;measureBeat<=lastBeatIndex;measureBeat++){if(((measureBeat%4)+4)%4!==0)continue;var measureTime=this.firstBeatDelay+measureBeat*beatSeconds,measureX=Math.round(LEFT+measureTime*this.pps-scrollX)+.5;p.moveTo(measureX,0);p.lineTo(measureX,h);}p.strokeStyle="#2764df";p.stroke();p.fillStyle="#333";p.font="10px Arial,'MS UI Gothic',sans-serif";for(var labelBeat=firstBeatIndex;labelBeat<=lastBeatIndex;labelBeat++){if(((labelBeat%4)+4)%4!==0)continue;var labelTime=this.firstBeatDelay+labelBeat*beatSeconds,labelX=LEFT+labelTime*this.pps-scrollX,measureNumber=Math.floor(labelBeat/4)+1;p.fillText(String(measureNumber),labelX+3,12);}var firstNote=this.findNoteStart(Math.max(0,start-this.maxNoteDuration)),lastNote=this.findNoteStart(end+1e-9);for(var index=firstNote;index<lastNote;index++){var n=this.noteIndex[index];if(n.pitch<PITCH_MIN||n.pitch>PITCH_MAX||n.end<start)continue;var noteX=LEFT+n.start*this.pps-scrollX,noteY=HEADER+(PITCH_MAX-n.pitch)*ROW+1,width=Math.max(2,(n.end-n.start)*this.pps);p.globalAlpha=this.muted.has(n.instrument)?.16:1;p.fillStyle=this.instrumentColors[n.instrument]||"#6f9fd8";p.fillRect(noteX,noteY,width,ROW-2);p.strokeStyle="rgba(0,45,105,.55)";p.strokeRect(noteX+.5,noteY+.5,Math.max(1,width-1),ROW-3);}p.globalAlpha=1;p.restore();};
  ResultSession.prototype.layoutPlayhead=function(){if(!this.playhead)return;var x=LEFT+this.position*this.pps-this.scroll.scrollLeft;this.playhead.style.transform="translate3d("+x.toFixed(2)+"px,0,0)";this.playhead.style.visibility=(x>=LEFT&&x<=this.viewportWidth)?"visible":"hidden";this.clock.textContent=this.position.toFixed(1)+"s";};
  ResultSession.prototype.dispose=function(){if(this.disposed)return;this.disposed=true;this.pause();if(this.hls)this.hls.destroy();if(this.audio){this.audio.pause();this.audio.removeAttribute("src");this.audio.load();}window.removeEventListener("music-to-midi-playback-start",this.onExternalPlayback);if(this.resizeObserver)this.resizeObserver.disconnect();cancelAnimationFrame(this.drawRaf);};
  function scan(){for(var i=sessions.length-1;i>=0;i--){if(!sessions[i].root.isConnected){sessions[i].dispose();sessions.splice(i,1);}}document.querySelectorAll(".msr-root:not([data-msr-init])").forEach(function(root){if(!root.querySelector(".msr-host"))return;root.setAttribute("data-msr-init","1");var s=new ResultSession(root);sessions.push(s);s.init();});}
  var timer=0;function schedule(){if(timer)return;timer=setTimeout(function(){timer=0;scan();},40);}new MutationObserver(function(changes){for(var i=0;i<changes.length;i++){for(var j=0;j<changes[i].addedNodes.length;j++){var n=changes[i].addedNodes[j];if(n.nodeType===1&&(n.matches(".msr-root")||n.querySelector(".msr-root"))){schedule();return;}}for(var k=0;k<changes[i].removedNodes.length;k++){var r=changes[i].removedNodes[k];if(r.nodeType===1&&(r.matches(".msr-root")||r.querySelector(".msr-root"))){schedule();return;}}}}).observe(document.documentElement,{childList:true,subtree:true});if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",schedule);else schedule();
})();
"""


def muscriptor_result_head() -> str:
    return (
        f"<style>{MUSCRIPTOR_RESULT_CSS}</style>"
        '<script src="/static/vendor/hls.min.js"></script>'
        f"<script>{MUSCRIPTOR_RESULT_JS}</script>"
    )

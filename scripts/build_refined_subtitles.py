"""Generate refined, short-segment subtitles for T1-01.
Splits each of the 33 shots into concise 3-5 second sentence cues,
producing:
  1. Bilingual SRT (.bilingual.srt)
  2. English only SRT (.en.srt, for YouTube CC)
  3. Chinese only SRT (.zh.srt, for Bilibili CC)
  4. ASS subtitle (.ass) with low margin (MarginV=26, small font 19pt)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

CONTENT_ROOT = Path(r"D:\CourseContent")
LESSON_SLUG = sys.argv[1] if len(sys.argv) > 1 else "t1-01-why-aerodynamics"
BUILD_DIR = CONTENT_ROOT / "build" / LESSON_SLUG
DELIVER_DIR = CONTENT_ROOT / "deliver" / LESSON_SLUG
META_PATH = BUILD_DIR / "audio" / "timeline_metadata.json"

def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, r = divmod(ms, 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def format_ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

# Manual precision pairings for all 33 shots to ensure 100% semantic alignment
PAIRS_PER_SHOT = {
    "shot-01-step-1": [
        ("An aircraft wing operates in pristine free air.", "飞机机翼运行在理想的自由空间。"),
        ("It slices through the atmosphere, recovers surface pressure smoothly, and keeps its boundary layer attached across ninety-five percent of the chord.", "它切开气流，表面压力平顺恢复，边界层全程附着。"),
        ("Its drag is almost entirely pure skin friction.", "阻力几乎全是纯表面摩擦。")
    ],
    "shot-01-step-2": [
        ("A road car is a completely different beast.", "汽车则是完全不同的生物。"),
        ("It has to package passengers and batteries within strict legal length limits.", "必须在法规长度和空间限制下布置乘员与电池。"),
        ("Air flowing over the roof cannot turn sharp corners at the back.", "车顶气流无法转过车尾急角。"),
        ("It tears away abruptly, trailing a massive, turbulent low-pressure wake.", "在尾端骤然断开，拖曳出一大团低压紊流尾迹。")
    ],
    "shot-01-step-3": [
        ("That wake sets the fundamental law of vehicle aerodynamics: over seventy percent of total resistance comes from base suction.", "这确立了基本定律：70%以上的阻力都来自车尾吸力。"),
        ("The job is not guiding smooth attached air — it is managing detachment and controlling the wake.", "工程师的任务不是追求附着流，而是控制分离与尾流拓扑。")
    ],
    "shot-02-step-1": [
        ("In a full-scale automotive wind tunnel, smoke streaklines reveal this split reality.", "在全尺寸汽车风洞中，烟线揭示了这种撕裂。"),
        ("As flow sweeps across the hood, windshield, and roof, the filaments stay remarkably straight and ordered.", "气流掠过机盖、风挡和车顶时，烟丝笔直有序。"),
        ("The boundary layer remains thin, stable, and obedient.", "边界层轻薄、稳定且服帖。")
    ],
    "shot-02-step-2": [
        ("Watch what happens at the roof trailing edge.", "注意车顶后缘——当下切角过大时，烟丝骤然脱扣。"),
        ("The moment the surface angles downward too aggressively, the smoke filaments let go.", "下切角过大时烟线失稳脱扣。"),
        ("The adverse pressure gradient overpowers the near-wall momentum, and the boundary layer snaps off into free shear.", "逆压梯度压垮了近壁面动量，边界层直接撕裂成自由剪切层。")
    ],
    "shot-02-step-3": [
        ("Behind the backlight, the smoke turns into an unresolved diffuse haze.", "在后挡风之后，烟雾化作一片白茫茫的扩散晕。"),
        ("Smoke streaks tell you exactly where flow detachment begins, but they leave the internal recirculating vortex cores completely hidden in the dark.", "烟线能标定分离起点，却看不清内部回流涡核。"),
        ("That is why physical smoke is only half the picture.", "所以物理实验只是故事的一半。")
    ],
    "shot-03-step-1": [
        ("Modern aerodynamics relies on closing the loop between physical testing and numerical simulation.", "现代气动工程仰赖实验与仿真的严密闭环。"),
        ("On the left, Mercedes-Benz wind tunnel photography captures real smoke streaklines, establishing ground-truth separation boundaries under full-scale Reynolds conditions.", "左侧奔驰风洞烟线确立了全尺寸工况下的客观物理分离边界。")
    ],
    "shot-03-step-2": [
        ("On the right, a CFD simulation cuts through the identical centerplane.", "右侧是高精度CFD切片。"),
        ("Simulation without physical validation is dangerous speculation.", "未经校核的仿真只是危险猜测；"),
        ("But when computed separation points match the tunnel smoke within millimeters, confidence in the numerical mesh is established.", "但当计算分离线与风洞实测毫米级吻合时，工程信任就此建立。")
    ],
    "shot-03-step-3": [
        ("The CFD slice exposes what the smoke could not: a massive closed recirculation bubble locked behind the rear glass.", "CFD切片揭示了肉眼看不见的流动：后窗后方锁死的大尺度闭合回流泡。"),
        ("Wind tunnel smoke proves where flow detaches; numerical computation reveals the pressure field and velocity vectors driving the drag.", "烟线证明脱扣位置，而数值解给出了主导阻力的压力场。")
    ],
    "shot-04-step-1": [
        ("Why can we not simply taper the rear into an elongated teardrop? Geometry prevents it.", "为什么不能把车尾拉成细长的水滴？几何不允许。"),
        ("A passenger car has a compact slenderness ratio of roughly three to one.", "汽车长高比仅约三比一。"),
        ("There is simply no chassis length available to taper flow gradually.", "在有限轴距内根本没有空间容许平缓收尾。")
    ],
    "shot-04-step-2": [
        ("The road surface introduces an even harsher constraint.", "地面施加了更残酷的边界。"),
        ("The underbody sits barely ten to twenty centimeters above tarmac.", "底盘离地仅十到二十厘米。"),
        ("Solid ground acts as an impermeable mirror wall, forcing underbody streamlines to violently converge into a Venturi channel and generating powerful asymmetric suction.", "地面宛如镜面固壁，强迫车底流线收缩进文丘里窄道并激发出强烈负压。")
    ],
    "shot-04-step-3": [
        ("On the road, tarmac rushes backward at vehicle speed — creating zero ground boundary layer.", "真实道路以车速相对后退，地面自身零边界层。"),
        ("Uncorrected static wind tunnel floors build artificial blockage.", "未修正的固定风洞地面会产生虚假边界层壅塞。"),
        ("Top-to-bottom geometric asymmetry, paired with moving-ground shear, means a car can never share the symmetric freedom of a wing.", "几何不对称叠加上地面剪切，注定汽车不可能享受机翼的自由对称流动。")
    ],
    "shot-05-step-1": [
        ("Every aerodynamicist must memorize this fundamental energy budget.", "这是每位工程师脑中必背的能量账本。"),
        ("For a modern passenger saloon, seventy to eighty percent of total aerodynamic drag is pressure drag — the net difference between forward stagnation thrust and rearward base suction.", "现代轿车70%到80%的总阻力都是压差阻力——源于车头高压与车尾低压吸力的静压差。")
    ],
    "shot-05-step-2": [
        ("Skin friction from air rubbing across smooth paint accounts for only ten to fifteen percent.", "光滑车漆的表面摩擦阻力仅占10%到15%。"),
        ("Polishing body panels to a mirror shine yields negligible highway gain.", "把车身抛光成镜面收益甚微。"),
        ("The wake suction dwarfs boundary layer shear stress by an order of magnitude.", "尾部负压吸力在量级上彻底碾压了摩擦剪切。")
    ],
    "shot-05-step-3": [
        ("Another eight to twelve percent is lost forcing air through heat exchangers in the engine bay.", "另有约8%到12%消耗在散热水箱的内流阻力上。"),
        ("That leaves the base wake as the prime target: the suction pulling on your trunk lid is kinetic energy permanently discarded to the atmosphere.", "真正的能耗大头永远在车尾——后备箱承受的负压吸力是被白白扔进大气的纯机械能。")
    ],
    "shot-06-step-1": [
        ("Automotive aerodynamics is far broader than chasing low wind resistance.", "气动工程远不止追求低风阻。"),
        ("We juggle four competing engineering mandates. First is energy economy.", "我们在四大相互打架的指标中走钢丝。第一是能耗。"),
        ("Aerodynamic power demand scales with the cube of vehicle speed — lowering drag coefficient by zero-point-zero-one delivers double-digit EV highway kilometers.", "风阻功率随车速三次方暴涨，降0.01风阻能多换十几公里高速续航。")
    ],
    "shot-06-step-2": [
        ("Second is high-speed stability. Airflow generates dynamic lift across both axles.", "第二是高速操稳。气流在前后轴产生气动升力。"),
        ("If rear lift rises unchecked, high-speed lane changes and crosswind gusts erode rear tire grip, inducing terrifying yaw instability and steering float.", "若后轴升力失控，高速变道和侧风会急剧削弱抓地力，导致横摆失稳与转向发飘。")
    ],
    "shot-06-step-3": [
        ("Third and fourth are acoustics and soiling management.", "第三和第四是风噪与防污。"),
        ("A-pillar vortices generate greenhouse wind rush that destroys cabin luxury.", "A柱螺旋涡会摧毁座舱静谧性。"),
        ("Meanwhile, road spray deposits blind mirrors, side windows, and autonomous driving sensors. Every exterior feature must serve all four masters.", "泥浆雨水会糊死后视镜与自动驾驶传感器。车身外形必须同时平衡这四大约束。")
    ],
    "shot-07-step-1": [
        ("What is the characteristic fluid scale of our discipline?", "我们的流动特征尺度在何处？"),
        ("A full-scale car cruising at highway speed operates in the ten-million Reynolds number regime.", "真车在高速巡航时处于一千万雷诺数量级。"),
        ("Under standard atmosphere, a four-and-a-half-meter car produces roughly one times ten to the seventh.", "在标准大气下，四米半的车长对应约10的7次方。")
    ],
    "shot-07-step-2": [
        ("Operating at ten million means the laminar boundary layer trips into fully developed turbulence within inches of the bumper.", "一千万雷诺数意味着层流在车头几厘米内就转变为全湍流。"),
        ("The near-wall viscous sublayer is fractions of a millimeter thick, packed with aggressive high-momentum turbulent shear.", "贴壁粘性底层不足一毫米，充满剧烈的高动量剪切。")
    ],
    "shot-07-step-3": [
        ("In this supercritical regime, flow separation is not dictated by delicate viscous transitions.", "在超临界流态下，分离点不取决于微弱的层流转捩。"),
        ("It is mechanically locked by geometry and adverse pressure slopes.", "而是被剧烈曲率和逆压梯度牢牢钉死。"),
        ("In scale wind tunnels, if you do not trip turbulence correctly, your separation lines become completely unrepresentative.", "若在缩尺风洞中未能正确人工触发湍流，吹出的分离线将完全失真。")
    ],
    "shot-08-step-1": [
        ("Never treat a vehicle as an isolated solid block. Air travels over it, through it, and inside it simultaneously.", "切忌把汽车当作实心积木。空气同时流经车表、穿透骨架、通达内部。"),
        ("External flow wraps the outer envelope, governing surface pressure, boundary layer growth, and large-scale wake vortex topology.", "外流包裹车身，主导表面压力场与大尺度尾涡形态。")
    ],
    "shot-08-step-2": [
        ("The second stream is cooling airflow.", "第二股是冷却流。"),
        ("Air must plunge through front intake grilles, negotiate dense radiator cores, and dump heat before spilling into the underbody and wheel wells.", "气流撞入进气格栅，费力穿透致密水箱散掉热量，再排入底盘或轮罩。"),
        ("That momentum loss drives our eight to twelve percent cooling drag.", "剧烈的动量损失贡献了8%到12%的冷却阻力。")
    ],
    "shot-08-step-3": [
        ("The third stream is cabin ventilation.", "第三股是座舱通风。"),
        ("High stagnation pressure at the windshield base pushes fresh air through the HVAC system, venting through hidden extractor flaps in the rear bumper.", "风挡根部高压将新鲜空气压入HVAC，再由后杠泄压阀排出。"),
        ("Modifying the exterior grille directly alters interior airflow and noise.", "车头开孔的微调会直接扰动乘员舱的气流与风噪。")
    ],
    "shot-09-step-1": [
        ("When airflow detaches from a vehicle, it follows two fundamental geometric pathways.", "气流脱离车身时遵循两类几何路径。"),
        ("The first is a transverse edge perpendicular to the flow — like a squared-off roofline.", "第一类是垂直于流向的横向棱边，如平直车顶横梁。"),
        ("Flow separates as a planar shear layer, feeding a dead-water recirculating wake.", "流动呈两维剪切层脱落，喂养出死水回流区。")
    ],
    "shot-09-step-2": [
        ("The second is a swept edge inclined to the flow — like an A-pillar or slanted C-pillar.", "第二类是斜向棱边，如倾斜的A柱与C柱。"),
        ("Crossflow rolling over that edge collapses under suction into concentrated, high-energy three-dimensional longitudinal vortices that drill straight back into the wake.", "横向侧翻流在吸力驱动下卷聚成强劲的高能三维纵向涡，笔直扎向车尾。")
    ],
    "shot-09-step-3": [
        ("Every production car wake is an interacting superposition of both modes.", "量产车尾流永远是这两种机制交织的叠加态。"),
        ("The downwash from C-pillar vortices pins flow to the rear glass on notchbacks, while fastbacks trade vortex drag for pressure recovery.", "C柱涡的下洗将气流按在三厢后窗上，快背则以涡阻力换取压力恢复。"),
        ("Understanding that interaction is the core of rear-end design.", "掌控这种权衡是车尾设计的灵魂。")
    ],
    "shot-10-step-1": [
        ("Novice aerodynamicists often ask why designers refuse to build frictionless teardrops.", "新人常问为何设计师不造零阻力水滴车。"),
        ("The answer is interior packaging and brand identity.", "答案是工程总布置与品牌辨识度。"),
        ("Passenger headroom, trunk luggage capacity, and wheel-arch dimensions define an immutable engineering envelope.", "乘客头部空间、后备箱容积和轮拱尺寸圈定了无法逾越的硬边界。")
    ],
    "shot-10-step-2": [
        ("Pedestrian crash regulations dictate front bumper height and hood clearance.", "行人碰撞法规钉死车头高度与发动机盖间隙。"),
        ("Battery packs dictate underbody floor thickness.", "电池包决定底盘厚度，散热器圈定进气口。"),
        ("An aerodynamicist works within hard physical boundaries, fighting for millimeter optimizations across frozen styling surfaces.", "工程师只能在已冻结的硬约束造型上，以毫米为单位抠出最优解。")
    ],
    "shot-10-step-3": [
        ("There is no universal aerodynamic ideal.", "世上不存在唯一的气动理想型。"),
        ("A notchback sedan, a fastback coupe, and a squareback estate represent three distinct compromises between packaging volume and drag.", "三厢、快背、旅行车与SUV，代表着容积与风阻的不同妥协。"),
        ("True engineering skill lies in optimizing whichever body architecture product planning selects.", "真正的工程功底，是在任何既定车身下交出极限表现。")
    ],
    "shot-11-step-1": [
        ("This brings us to the core philosophy of our discipline.", "这确立了全书的第一哲学。"),
        ("Step one: accept bluff reality.", "第一步：认清钝体现实。"),
        ("A road vehicle is fundamentally a blunt object.", "汽车天生是钝体，流动分离不可避免。"),
        ("Separation cannot be avoided, and chasing fully attached flow everywhere is futile.", "徒劳追求全车附着流注定碰壁。")
    ],
    "shot-11-step-2": [
        ("Step two: anchor your separation lines.", "第二步：主动锚定分离线。"),
        ("If flow separates over a smooth curve, the detachment line wanders unpredictably with wind gusts and vehicle pitch.", "气流若在圆润曲面上分离，脱扣点会随阵风与俯仰无常漂移；"),
        ("Adding a sharp spoiler edge locks the separation line permanently in space.", "用锋利的尾部小鸭尾，能将分离线死死钉在空间原点。")
    ],
    "shot-11-step-3": [
        ("Step three: sculpt wake vortex topology.", "第三步：雕刻尾涡拓扑。"),
        ("Use diffuser upsweep, boat-tailing, and side tapers to squeeze wake volume and maximize rear pressure recovery.", "利用扩散器上挑和侧面内收挤压尾流截面，最大限度拉回车尾背压。"),
        ("In our next lesson, we will calculate the physics and economic ledger of drag coefficient and velocity cubed.", "下一节，我们来细算风阻与车速三次方背后的经济账本。")
    ]
}

def generate_subtitles():
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    shots = meta["shots"]
    all_cues = []
    
    for shot in shots:
        shot_id = shot["shot_id"]
        t_start = shot["start_time_s"]
        t_end = shot["end_time_s"]
        duration = t_end - t_start
        
        pairs = PAIRS_PER_SHOT.get(shot_id)
        if not pairs:
            # Fallback single cue if not specified
            pairs = [(shot["en"], shot["zh"])]
            
        # Allocate time proportional to word count of English
        word_counts = [max(1, len(en.split())) for en, zh in pairs]
        total_words = sum(word_counts)
        
        cur_t = t_start
        for idx, (en, zh) in enumerate(pairs):
            ratio = word_counts[idx] / total_words
            cue_dur = duration * ratio
            cue_start = cur_t
            cue_end = cur_t + cue_dur
            cur_t = cue_end
            
            all_cues.append({
                "index": len(all_cues) + 1,
                "start_s": cue_start,
                "end_s": cue_end,
                "en": en,
                "zh": zh
            })
            
    print(f"Generated {len(all_cues)} refined short-form cues!")
    
    # 1. Bilingual SRT
    srt_bilingual = BUILD_DIR / "subtitles" / "t1-01-narration-en-zh.srt"
    with open(srt_bilingual, "w", encoding="utf-8") as f:
        for cue in all_cues:
            f.write(f"{cue['index']}\n")
            f.write(f"{format_srt_time(cue['start_s'])} --> {format_srt_time(cue['end_s'])}\n")
            f.write(f"{cue['en']}\n{cue['zh']}\n\n")
            
    # 2. English Only SRT (YouTube CC)
    srt_en = DELIVER_DIR / f"{LESSON_SLUG}.en.srt"
    with open(srt_en, "w", encoding="utf-8") as f:
        for cue in all_cues:
            f.write(f"{cue['index']}\n")
            f.write(f"{format_srt_time(cue['start_s'])} --> {format_srt_time(cue['end_s'])}\n")
            f.write(f"{cue['en']}\n\n")
            
    # 3. Chinese Only SRT (Bilibili CC)
    srt_zh = DELIVER_DIR / f"{LESSON_SLUG}.zh.srt"
    with open(srt_zh, "w", encoding="utf-8") as f:
        for cue in all_cues:
            f.write(f"{cue['index']}\n")
            f.write(f"{format_srt_time(cue['start_s'])} --> {format_srt_time(cue['end_s'])}\n")
            f.write(f"{cue['zh']}\n\n")
            
    # Copy bilingual to deliver
    srt_bilingual_deliver = DELIVER_DIR / f"{LESSON_SLUG}.bilingual.srt"
    import shutil
    shutil.copy2(srt_bilingual, srt_bilingual_deliver)
    
    # 4. ASS Subtitle (for burning and external players)
    # 1080P resolution, compact font size (19), low bottom margin (MarginV=24)
    # Alignment 2 = bottom center, BorderStyle 1 = outline + drop shadow
    ass_path = DELIVER_DIR / f"{LESSON_SLUG}.ass"
    ass_build = BUILD_DIR / "subtitles" / f"{LESSON_SLUG}.ass"
    
    ass_content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00111111,&H80000000,-1,0,0,0,100,100,0,0,1,1.5,0.8,2,80,80,24,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    
    for cue in all_cues:
        st = format_ass_time(cue["start_s"])
        et = format_ass_time(cue["end_s"])
        # Format English on top (smaller font or plain), Chinese on bottom
        text = f"{cue['en']}\\N{cue['zh']}"
        ass_content.append(f"Dialogue: 0,{st},{et},Default,,0,0,0,,{text}")
        
    ass_text = "\n".join(ass_content) + "\n"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_text)
    with open(ass_build, "w", encoding="utf-8") as f:
        f.write(ass_text)
        
    print(f"[Done] Exported subtitles to {DELIVER_DIR}:")
    print(f"  • {srt_bilingual_deliver.name}")
    print(f"  • {srt_en.name}")
    print(f"  • {srt_zh.name}")
    print(f"  • {ass_path.name}")

if __name__ == "__main__":
    generate_subtitles()

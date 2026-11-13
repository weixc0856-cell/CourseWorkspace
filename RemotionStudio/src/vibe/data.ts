export type Shot = {
  id: string;
  from: number;
  to: number;
  chapter: string;
  kicker: string;
  captionEn: string;
  captionZh: string;
  accent: string;
};

export const SHOTS: Shot[] = [
  {
    id: 'hook',
    from: 0,
    to: 450,
    chapter: '01 / THE OBJECT',
    kicker: 'PLASMA ETCH',
    captionEn: 'Your phone is a city of twenty billion switches.',
    captionZh: '你的手机，是一座由两百亿个开关组成的城市。',
    accent: '#5FF3FF',
  },
  {
    id: 'scale',
    from: 450,
    to: 844,
    chapter: '02 / THE SCALE',
    kicker: 'A FEW NANOMETRES',
    captionEn: 'A few nanometres wide — tens of thousands of times thinner than a hair.',
    captionZh: '几纳米宽，比一根头发细几万倍。',
    accent: '#8B5CFF',
  },
  {
    id: 'iso',
    from: 844,
    to: 1406,
    chapter: '03 / THE PROBLEM',
    kicker: 'ISOTROPIC ETCH',
    captionEn: 'Wet etching is isotropic. It eats sideways and undercuts the mask.',
    captionZh: '湿法刻蚀是各向同性的，它会从侧面掏空掩膜。',
    accent: '#FF5566',
  },
  {
    id: 'breakdown',
    from: 1406,
    to: 1800,
    chapter: '04 / THE TRICK',
    kicker: 'ION-ENHANCED',
    captionEn: 'To carve straight down, we need a second ingredient: ions.',
    captionZh: '想垂直刻下去，我们需要第二种东西：离子。',
    accent: '#8B5CFF',
  },
  {
    id: 'directional',
    from: 1800,
    to: 2362,
    chapter: '05 / THE METHOD',
    kicker: 'PASSIVATION',
    captionEn: 'Ions open the floor. A polymer film protects the walls.',
    captionZh: '离子打开底部，聚合物薄膜保护侧壁。',
    accent: '#5FF3FF',
  },
  {
    id: 'bosch',
    from: 2362,
    to: 3094,
    chapter: '06 / THE PATTERN',
    kicker: 'BOSCH PROCESS',
    captionEn: 'The Bosch cycle: etch, deposit, repeat. Each cycle leaves a scallop.',
    captionZh: 'Bosch 循环：刻蚀、沉积、重复。每一轮都留下一道扇贝。',
    accent: '#FF4D9D',
  },
  {
    id: 'loading',
    from: 3094,
    to: 3366,
    chapter: '07 / THE FAILURES',
    kicker: 'FAILURE 01',
    captionEn: 'Micro-loading: dense patterns starve. Narrow trenches etch slower.',
    captionZh: '微观负载：图形越密，反应物越少，窄槽刻得更慢。',
    accent: '#FFB84D',
  },
  {
    id: 'grass',
    from: 3366,
    to: 3637,
    chapter: '07 / THE FAILURES',
    kicker: 'FAILURE 02',
    captionEn: 'Grass: micromasks shield patches of silicon, leaving pillars.',
    captionZh: '长草：微掩膜护住局部硅，刻完只剩一根根硅柱。',
    accent: '#FFB84D',
  },
  {
    id: 'notch',
    from: 3637,
    to: 3909,
    chapter: '07 / THE FAILURES',
    kicker: 'FAILURE 03',
    captionEn: 'Notching: charge bends ions sideways at the oxide interface.',
    captionZh: '缺口：电荷在氧化层界面把离子拐向侧壁。',
    accent: '#FF5566',
  },
  {
    id: 'payoff',
    from: 3909,
    to: 4500,
    chapter: '08 / THE RESULT',
    kicker: 'HIGH-ASPECT-RATIO',
    captionEn: 'Aspect ratios beyond 100:1. Two hundred layers. One chip.',
    captionZh: '深宽比超过 100:1，两百多层，堆出一颗芯片。',
    accent: '#5FF3FF',
  },
  {
    id: 'end',
    from: 4500,
    to: 4560,
    chapter: 'END',
    kicker: 'SIMULATION',
    captionEn: 'A qualitative simulation of plasma etching, not a calibrated tool.',
    captionZh: '这是一段等离子刻蚀的定性模拟，不是经过标定的工具。',
    accent: '#5FF3FF',
  },
];

export const FACTS = {
  transistors: '20B',
  node: '3 NM',
  hair: '30,000×',
  aspect: '100:1',
  layers: '200+',
};

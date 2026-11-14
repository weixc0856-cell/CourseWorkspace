import {BAR} from './theme';

const B = (k: number) => +(k * BAR).toFixed(3);

export const T = {
  hook: 0,
  hookEnd: B(4),
  question: B(4),
  earlier: B(7),
  quote: B(10),
  ridge: B(14),
  sim: B(18),
  chart: B(22),
  water: B(26),
  village: B(30),
  quote2: B(34),
  name: B(40),
  qi: B(45),
  book: B(50),
  limit: B(54),
  four: B(58),
  return: B(62),
  question2: B(70),
  end: B(74),
  endEnd: 152,
};

export type Caption = {en: string; zh: string; size?: number; top?: number; note?: string};

export const CAPTIONS: Record<string, Caption[]> = {
  hook: [{en: 'TWO CHARACTERS. ONE INSTRUCTION.', zh: '风水，两个字：风，水。'}],
  question: [{en: 'WHERE DOES THE WORD COME FROM?', zh: '这个词是从哪儿来的？'}],
  earlier: [
    {en: 'BEFORE THE WORD, THERE WAS THE PRACTICE.', zh: '在「风水」这个词出现之前，先有相地。'},
  ],
  quote: [{en: 'QI SCATTERS IN WIND. IT STOPS AT WATER.', zh: '这是「风水」二字已知最早的出处。'}],
  ridge: [{en: 'A RIDGE IS A WALL.', zh: '山脊是一堵墙。'}],
  sim: [{en: 'BEHIND IT, THE WIND DROPS.', zh: '风在背面慢下来。'}],
  chart: [{en: '2× AT THE CREST. 0.4× BEHIND IT.', zh: '山顶是开阔地的两倍，背后只剩四成。'}],
  water: [{en: 'WATER STOPS WHAT WIND SCATTERS.', zh: '风把气吹散，水让它停下。'}],
  village: [{en: 'HIDE FROM THE WIND. SIT BY THE WATER.', zh: '挡住风，靠近水。'}],
  quote2: [{en: 'WATER FIRST. WIND SECOND.', zh: '同一部书里，水的分量排在风之前。'}],
  name: [{en: 'THE NAME IS THE INSTRUCTION.', zh: '所以这个名字本身就是一句指令。'}],
  qi: [{en: 'QI IS NOT AIR.', zh: '原文里的「气」，不等于空气。'}],
  book: [{en: 'THE BOOK IS NOT BY GUO PU.', zh: '《葬书》旧题郭璞，学界多认为是宋人托名。'}],
  limit: [{en: 'NOT EVERY RULE CAN BE MEASURED.', zh: '不是每条口诀都能被测量。'}],
  four: [{en: 'WIND. SUN. WATER. SOIL.', zh: '能测的有四样：风、日照、水、土。'}],
  return: [
    {en: 'TAKE AWAY THE MYSTERY.', zh: '去掉神秘。'},
    {en: 'THE LAND REMAINS.', zh: '地还在。'},
  ],
  question2: [{en: 'IT WAS A QUESTION ABOUT THE GROUND.', zh: '它本来是一个关于土地的问题。'}],
};

export const SERIES_EN = 'FENG SHUI: THE IDEAS BEHIND THE LANDSCAPE';
export const SERIES_ZH = '风水背后的中国智慧';
export const EPISODE_ZH = '第 01 集 · 风水为什么叫风水';
export const EPISODE_EN = 'EP 01 · WHY IT IS CALLED WIND-WATER';

/**
 * 麦肯锡橙白配色与字体令牌。
 * 与 CourseSlides/css/mckinsey-orange.css 的 :root 变量一一对应，改一处两边同步。
 */
export const MK = {
  white: '#FFFFFF',
  text: '#1A1A1A',
  muted: '#595959',
  orange: '#EB6100',
  orangeSoft: '#FFF5F0',
  border: '#E5E5E5',
  danger: '#E53E3E', // 仅用于阻断/危险语义，不在常规五色内
  dangerSoft: '#FDE8E8',
  success: '#2E7D32', // 仅用于命中/成功语义
  successSoft: '#F2FBF4',
  codeBg: '#FAFAFA',
} as const;

export const MK_FONT_SANS = '"Segoe UI", "Helvetica Neue", Arial, sans-serif';
export const MK_FONT_MONO = '"Cascadia Mono", Consolas, monospace';

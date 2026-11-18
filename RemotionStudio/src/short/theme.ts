import themes from '../../../shared/design-tokens/themes.json';
import tokens from '../../../shared/design-tokens/tokens.json';

export type ThemeColors = {
  name: string;
  light: boolean;
  paper: string;
  surface: string;
  ink: string;
  body: string;
  muted: string;
  border: string;
  accent: string;
  blue: string;
  teal: string;
  purple: string;
  red: string;
  white: string;
  sans: string;
  serif: string;
  mono: string;
};

export function resolveTheme(name?: string): ThemeColors {
  const key =
    name && Object.prototype.hasOwnProperty.call(themes.themes, name)
      ? name
      : themes.default;
  const theme = (themes.themes as Record<string, {colors: Record<string, string>; light: boolean}>)[key];
  return {
    name: key,
    light: theme.light,
    ...(theme.colors as Omit<ThemeColors, 'name' | 'light' | 'white' | 'sans' | 'serif' | 'mono'>),
    white: tokens.colors.white,
    sans: tokens.fonts.sans,
    serif: tokens.fonts.serif,
    mono: tokens.fonts.mono,
  };
}

const COLOR_ROLES = new Set([
  'paper',
  'surface',
  'ink',
  'body',
  'muted',
  'border',
  'accent',
  'blue',
  'teal',
  'purple',
  'red',
  'white',
]);

export function resolveColor(theme: ThemeColors, value?: string): string | undefined {
  if (!value) {
    return undefined;
  }
  if (value.startsWith('#')) {
    return value;
  }
  return COLOR_ROLES.has(value) ? (theme as unknown as Record<string, string>)[value] : value;
}

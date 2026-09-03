export type ThemePref = 'system' | 'light' | 'dark';

const KEY = 'performance.theme';

/**
 * Reading and writing the theme choice.
 *
 * "system" removes the attribute entirely rather than resolving it, so the
 * page keeps following the OS if the reader changes it while the tab is open.
 */
export const getTheme = (): ThemePref => {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch {
    return 'system';
  }
};

export const applyTheme = (pref: ThemePref): void => {
  const root = document.documentElement;
  if (pref === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', pref);
  try {
    if (pref === 'system') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* Private browsing, or storage disabled: the choice simply will not persist. */
  }
};

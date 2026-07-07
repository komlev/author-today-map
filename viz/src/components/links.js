import {html} from "npm:htl";

// rel="noopener noreferrer" so clicking through from a leaderboard row
// never leaks this site's URL (or a window.opener handle) to author.today.
export function linkCell(label, url) {
  return url ? html`<a href=${url} target="_blank" rel="noopener noreferrer">${label}</a>` : label;
}

// Inputs.table's default per-column formatter coerces every non-number,
// non-Date cell value with a template literal (`${value}`) before the
// Node-vs-text check that would otherwise let a DOM node through as-is.
// For an <a> element that coercion doesn't yield "[object HTMLAnchorElement]"
// as you'd expect — HTMLAnchorElement implements the HTMLHyperlinkElementUtils
// stringifier, so `${anchorEl}` silently returns anchorEl.href, and the link
// text is quietly replaced by the raw URL. Passing this identity function as
// the column's `format` bypasses that auto-formatter so linkCell()'s node
// reaches the table unchanged.
export const identity = (value) => value;

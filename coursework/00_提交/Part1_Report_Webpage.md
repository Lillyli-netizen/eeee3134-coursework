# Coursework Part I Report: Personal Webpage Development

**Student:** Olivia Li (李月艺)
**Module:** EEEE3134
**Date:** November 2026

## Published Webpages

- **Version 1 (AI-Generated):** https://lillyli-netizen.github.io/AI-generated-page/
- **Version 2 (AI-Guided / Self-Designed):** https://lillyli-netizen.github.io/Me-designed-page/

---

## 1. Development Process

### 1.1 Version 1 — AI-Generated Webpage

Version 1 was produced with minimal human design input. I gave the AI coding agent a single
high-level instruction — "build a personal homepage for an AI/CS student" — and deliberately let
the agent make almost all design and implementation decisions on its own.

The agent returned a complete, working single-page site in one pass:

- **Structure:** a fixed top navigation bar with a hamburger menu for mobile, followed by four
  sections (Hero, About, Skills, Projects) and a contact footer, all implemented as a
  `index.html` + `style.css` + `script.js` trio.
- **Visual style:** a light, card-based layout with a friendly, informal tone (emoji section
  headers, conversational copy such as "trying to figure out why my model's loss isn't
  decreasing").
- **Implementation steps:** the agent chose the tech stack (plain HTML/CSS/JS, Google Fonts
  `Inter`), generated the colour palette and spacing system, wrote the responsive breakpoints,
  and even invented placeholder content for the project cards.

My involvement at this stage was limited to reviewing the output and publishing it to the
`AI-generated-page` repository with GitHub Pages. No design specifications were provided by me;
every decision — layout, palette, typography, copy, and file organisation — was made by the AI.

### 1.2 Version 2 — AI-Guided Webpage (Detailed Human Specifications)

Version 2 was built the opposite way: I first decided what I wanted, then instructed the AI
step by step, and reviewed every iteration in a real browser. My specifications covered layout,
content, visual style, and functionality:

- **Layout:** a fixed left sidebar (avatar, name, role, navigation, theme/language buttons) with
  a centred main column; a typewriter hero followed by numbered sections (01 About / 02 Tech
  Stack / 03 Recent Competitions / 04 Research Projects / 05 Contact) following a
  developer-portfolio convention rather than a generic template.
- **Visual style:** two complete themes driven by CSS custom properties (`--bg`, `--accent`,
  `--border`, …) — a cold dark theme by default and a warm cream light theme — with monospace
  accents (JetBrains Mono) for section numbers and buttons, and a typewriter hero headline with
  a blinking cursor. The competition section deliberately breaks the clean grid: cards are
  slightly rotated, held down by strips of "tape", and annotated in a handwriting font
  (Caveat), like notes pinned to a board.
- **Content:** real personal data only — my actual education history (BSc in Big Data,
  Shandong Agricultural University; incoming MSc ECCE at UNNC), my real research interests
  (object detection, LLM-based vehicle control), three real competition entries with
  verifiable scores (79.40/100 in a Tianchi table-understanding contest, 56.8% success rate
  in the LingBot-VLA embodied-AI challenge, 0.305 balanced accuracy in Kaggle's Name That
  LLM), and live statistics from my CSDN blog (51 original posts, 16,000+ views, 199
  favourites) instead of AI-invented placeholders.
- **Functionality:** dark/light theme toggle and Chinese/English language toggle, both
  persisted in `localStorage`; skill bars that animate only when scrolled into view (triggered
  by an `IntersectionObserver`, one observer per skill group).

Because I specified requirements in detail, development became an iterative loop rather than a
single generation. The most instructive iteration was a bug I found during browser testing:
after clicking the theme button, nothing happened and the skill bars never animated. The
browser console showed `ReferenceError: Cannot access 'themeBtn' before initialization` — a
temporal dead zone (TDZ) error. A translation-refresh function called `updateThemeBtn()` before
the `const themeBtn` declaration had been evaluated, and because the exception aborted the rest
of the script, every listener registered after that point (theme toggle, scroll observers) was
silently never attached. Moving the declaration above the first function call fixed both
symptoms at once. This single bug taught me more about JavaScript execution order than any
tutorial, and it only surfaced because I tested the page manually instead of trusting the
generated code.

Further iterations were driven entirely by my own review of the rendered page: reworking the
light theme from a plain white into a warm cream palette after the first attempt looked
"clinical"; adding a full Chinese/English i18n layer (each UI label is a key in a bilingual
dictionary) under the hard constraint that the English view must contain no Chinese
characters at all; replacing the avatar letter with a real photo cropped to a 160px square;
re-centring the content column with `max(280px, calc((100% - 900px) / 2))` so it stays
balanced at every viewport width; moving the exploratory LLM-vehicle project card to the end
of the research list; and redesigning the flat competition cards with hand-drawn accents
after they felt impersonal. Every change was verified locally (`python -m http.server`) in
both themes and both languages before pushing to GitHub Pages, with cache-busting query
strings (`style.css?v=9`) to force browsers to pick up the latest files.

---

## 2. Comparison and Evaluation

| Aspect            | Version 1 (AI-generated)                                                       | Version 2 (AI-guided)                                                                                          |
| ----------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Design            | Generic card template; pleasant but interchangeable                            | Custom dual-theme visual system (CSS variables, sidebar, monospace accents, hand-drawn competition cards) matched to a stated style goal |
| Content           | Partly invented by the AI ("I'm an AI & CS Student" — not my actual programme) | Verified personal data: real education history, three real competition scores, real blog statistics        |
| Functionality     | Static content + mobile menu                                                   | Theme & language switching with persistence, scroll-triggered animations, typewriter effect                    |
| Development speed | One prompt, one pass — fastest path to a working site                          | Multiple iterations across several sessions                                                                    |
| Debugging effort  | Almost none needed                                                             | Real debugging required (TDZ error), diagnosed via browser console                                             |
| Human involvement | Low: I reviewed and published                                                  | High: I defined layout/content/style/behaviour, reviewed every change in a browser, and decided each iteration |

**What the comparison shows.** Version 1 demonstrates how far a single prompt gets you: the
result is complete, responsive, and immediately publishable, and for a throwaway page it would
be good enough. Its weakness is authenticity — the AI filled unknowns with plausible-sounding
generic content, so the page describes a student who does not quite exist.

Version 2 shifted my role from reviewer to director. The cost was real: more sessions, a
genuine bug to diagnose, and careful cross-checking of every text string in two languages
(each UI label exists as a key in a bilingual dictionary, so the translation table itself had
to stay consistent). The benefit was a page that is actually mine: correct facts, a visual
identity I chose, and features I specified. In terms of the level of human involvement, the two
versions sit at opposite ends — and the quality gap tracks that involvement almost linearly.

The most important technical lesson from Version 2: generated code is not verified code. The
TDZ bug produced no build warning and only manifested as silent dead UI, which I would never
have caught without opening the browser console myself.

---

## 3. Personal Reflection

<!-- ⚠️ 以下 Personal Reflection 一节必须由本人撰写（课程规定 AI 禁写）。
     写作引导问题（用自己的话回答，不必全部回答）：
     1. 两个版本做完，你对"用 AI 做开发"的最大感受是什么？和你的预期一致吗？
     2. Version 1 里 AI 替你做的哪个决定，你其实不认同但当时接受了？
     3. Version 2 的 TDZ bug 排查过程给你什么启发？如果没有浏览器报错，你会怎么办？
     4. 这次经历会如何改变你以后给 AI 下指令的方式？（对比一次生成 vs 多轮迭代的体验）
     5. 你认为 AI 辅助开发中，人的不可替代的部分是什么？
     建议写 200–400 词英文或等量中文，口语化、真诚即可，忌套话。 -->

*[To be completed personally — AI assistance is prohibited for this section per course policy.]*

---

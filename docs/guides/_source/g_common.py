"""Helpers for the PMC guide library: small functions that write the guide HTML."""
import html as _h
import json

E = _h.escape
USED = set()          # images referenced by the guide being built
PICKS = set()         # images an image-picker needs in DATA.images

DATE = "20261006"      # the edition being built; see _source/README.md
PREV = "20261005"      # the edition it supersedes
GUIDES = []           # filled by the g_*.py modules: dicts with slug, file, title, ...


def fname(slug):
    return f"PMC_Dada_PSA_{slug}_Guide_{DATE}.html"


def S(id, group, title, *parts, who=(), roles="", eyebrow=None):
    chips = "".join(f"<span>{E(w)}</span>" for w in who)
    return (f'<section class="s" id="{id}" data-group="{E(group)}" data-title="{E(title)}"'
            + (f' data-roles="{roles}"' if roles else "") + ">"
            f'<div class="s__head"><div><div class="s__eyebrow">{E(eyebrow or group)}</div><h2>{E(title)}</h2></div>'
            f'<div class="who">{chips}</div></div>' + "".join(parts)
            + '<button class="done-btn" aria-pressed="false"><i></i>Mark as read</button></section>')


def LEAD(t):
    return f'<p class="lead">{t}</p>'


def P(t):
    return f"<p>{t}</p>"


def H(t):
    return f"<h3>{E(t)}</h3>"


def UL(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def STEPS(items):
    return '<ol class="steps">' + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


ICON = {"info": "i-info", "good": "i-check", "warn": "i-alert"}


def NOTE(kind, t):
    return f'<div class="note {kind}"><svg><use href="#{ICON[kind]}"/></svg><p>{t}</p></div>'


def GRID(pairs):
    return '<div class="grid">' + "".join(f'<div class="tile"><b>{E(a)}</b><span>{b}</span></div>' for a, b in pairs) + "</div>"


def TABLE(head, rows):
    return ('<div class="tw"><table><thead><tr>' + "".join(f"<th>{E(h)}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


def DET(pairs):
    return "".join(f"<details><summary>{E(q)}</summary><div>{a}</div></details>" for q, a in pairs)


def FIG(img, cap="", alt=None):
    USED.add(img)
    return (f'<figure><div class="shot"><img src="%%IMG:{img}%%" alt="{E(alt or cap or img)}" loading="lazy">'
            f'<span class="zoom">Click to enlarge</span></div>' + (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>")


def TOUR(key, img=None):
    USED.add(img or key)
    return (f'<div class="tour" data-tour="{key}"><div class="shot"><img src="%%IMG:{img or key}%%" alt="{E(key)}"></div>'
            '<div class="tour__panel"><div class="tour__n">1</div><div class="tour__txt"></div>'
            '<div class="tour__nav"><button data-d="-1">Back</button><button data-d="1">Next</button></div></div></div>'
            '<p style="font-size:13px;color:var(--text-3);margin-top:-6px">Click the numbered dots, or use Back and Next.</p>')


def WIDGET(title, inner, w, cfg=None):
    c = f'<script type="application/json" class="cfg">{json.dumps(cfg)}</script>' if cfg is not None else ""
    return (f'<div class="widget" data-w="{w}"><div class="widget__title"><svg><use href="#i-spark"/></svg>{E(title)}</div>'
            f"{c}{inner}</div>")


def OPTS(pairs, cls="opt", attr="data-k"):
    return '<div class="opts">' + "".join(f'<button class="{cls}" {attr}="{E(k)}">{E(v)}</button>' for k, v in pairs) + "</div>"


def CHOOSER(title, options):
    """options: [(key, button label, html shown)]"""
    return WIDGET(title, OPTS([(k, b) for k, b, _ in options]) + '<div class="w-out out"><span style="color:var(--text-3)">Pick the one that fits.</span></div>'
                  + "".join(f'<template data-k="{k}">{h}</template>' for k, _, h in options), "chooser")


def STEPPER(title, start, states, intro=""):
    return WIDGET(title, (P(intro) if intro else "") + '<div class="w-out out"></div>', "stepper", {"start": start, "states": states})


def IMGPICK(items, first_cap=""):
    """items: [(img, label, caption)]"""
    for i, _, _ in items:
        PICKS.add(i)
    btns = "".join(f'<button class="opt" data-img="{i}" data-cap="{E(c)}">{E(l)}</button>' for i, l, c in items)
    return (f'<div data-w="imgpick"><div class="opts" style="margin:10px 0">{btns}</div>'
            f'<figure><div class="shot"><img src="%%PICK:{items[0][0]}%%" alt="{E(items[0][1])}"><span class="zoom">Click to enlarge</span></div>'
            f"<figcaption>{E(items[0][2])}</figcaption></figure></div>")


def QUIZ():
    return '<div data-w="quiz" class="quiz"></div>'


def HERO(title, text, meta=(), accent="blue"):
    grad = "var(--blue) 0%,var(--blue-l) 100%"
    return (f'<div class="hero" style="background:linear-gradient(120deg,{grad})"><h1>{E(title)}</h1><p>{text}</p>'
            '<div class="hero__meta">' + "".join(f"<span>{E(m)}</span>" for m in meta) + "</div></div>")


def LIBRARY(current=None):
    cards = []
    for g in GUIDES:
        if g["slug"] == current:
            continue
        cls = " fin" if g.get("kind") == "fin" else " req" if g.get("kind") == "req" else ""
        cards.append(f'<a class="{cls.strip()}" href="{fname(g["slug"])}"><b>{E(g["title"])}</b><span>{E(g["blurb"])}</span>'
                     f'<em>For {E(g["for"])}</em></a>')
    return '<div class="library">' + "".join(cards) + "</div>"

"""Trilha, sound design e mixagem do filme v2 (síntese própria, 48 kHz estéreo).

Lê src/linha.json (tempos das falas) e gera:
  public/audio/mix_final.wav        trilha + efeitos + narração
  public/audio/mix_sem_narracao.wav trilha + efeitos
Uso: python scripts/trilha.py   (precisa de numpy, scipy, soundfile)
"""
import json
import os
import numpy as np
import soundfile as sf
from scipy import signal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINHA = json.load(open(os.path.join(RAIZ, 'src', 'linha.json'), encoding='utf-8'))
SR = 48000
DUR = LINHA['duracao']
N = int(SR * DUR)
rng = np.random.default_rng(2026)
T = np.arange(N) / SR
BEAT = 0.5          # 120 BPM
GRID0 = 0.25        # batidas em x,25 / x,75 (impacto do logo em 6,75)


def nt(name):
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3, 'G': -2, 'G#': -1, 'A': 0, 'Bb': 1, 'B': 2}
    return 440.0 * 2 ** ((names[name[:-1]] + 12 * (int(name[-1]) - 4)) / 12)


def buf():
    return np.zeros((N, 2))


def place(dst, x, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if x.ndim == 1:
        x = np.stack([x * np.cos((pan + 1) * np.pi / 4), x * np.sin((pan + 1) * np.pi / 4)], 1) * np.sqrt(2)
    i1 = min(N, i0 + len(x))
    if i1 <= max(i0, 0):
        return
    s = max(0, -i0)
    dst[max(i0, 0):i1] += x[s:i1 - i0] * gain


def lp(x, fc, o=2):
    return signal.sosfilt(signal.butter(o, min(fc, SR * 0.45), 'low', fs=SR, output='sos'), x, axis=0)


def hp(x, fc, o=2):
    return signal.sosfilt(signal.butter(o, fc, 'high', fs=SR, output='sos'), x, axis=0)


def bp(x, f1, f2, o=2):
    return signal.sosfilt(signal.butter(o, [f1, min(f2, SR * 0.45)], 'band', fs=SR, output='sos'), x, axis=0)


def sweep(x, curve, kind='low', block=256):
    y = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        fc = float(np.clip(curve[min(i, len(curve) - 1)], 30, SR * 0.45))
        sos = signal.butter(2, fc, kind, fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2) + x.shape[1:])
        y[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], axis=0, zi=zi)
    return y


def saw(f, n, ph=0.0):
    p = (ph + np.cumsum(np.full(n, f) / SR)) % 1.0
    return 2 * p - 1


def noise(n):
    return rng.standard_normal(n)


def make_ir(sec, damp):
    n = int(sec * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 6.9 / sec)[:, None]
    ir = lp(ir, damp)
    ir[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))[:, None]
    return ir / np.sqrt((ir ** 2).sum(0))


IR, IR_SALA = make_ir(3.0, 6000), make_ir(0.6, 7000)


def reverb(x, ir=IR):
    return np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)


def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))


# =============================================================== MÚSICA
mus = buf()


def pad(freqs, t0, t1, c0, c1, g, fi=1.0, fo=1.0, det=0.12):
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for f in freqs:
        for k, d in enumerate([-det, -det / 3, det / 3, det]):
            w = saw(f * 2 ** (d / 24), n, rng.random())
            pan = [-0.7, -0.25, 0.25, 0.7][k]
            out[:, 0] += w * np.cos((pan + 1) * np.pi / 4)
            out[:, 1] += w * np.sin((pan + 1) * np.pi / 4)
    out /= len(freqs) * 4
    out = sweep(out, c0 * (c1 / c0) ** (t / t[-1]))
    e = np.minimum(1, t / fi) * np.minimum(1, (t[-1] - t) / fo)
    place(mus, out * e[:, None] * g, t0)


# harmonia: Ré menor (abertura) -> Sib (Falkyria/dados) -> Fá/Lá (Lumen) -> Sol m9 (Nicx) -> Sib -> Dó sus -> Ré m add9
pad([nt('D2'), nt('A2'), nt('D3')], 0.0, 6.9, 120, 900, 0.5, fi=1.2, fo=0.3)
pad([nt('F3'), nt('A3'), nt('E4')], 3.0, 6.85, 400, 2200, 0.2, fi=1.5, fo=0.2)
pad([nt('Bb1'), nt('F2'), nt('D3'), nt('A3')], 6.75, 14.35, 700, 1600, 0.42, fi=0.05, fo=0.2)
pad([nt('F1'), nt('C2'), nt('A2'), nt('E3'), nt('G3')], 14.3, 21.7, 900, 1800, 0.38, fi=0.05, fo=0.3)
pad([nt('G1'), nt('D2'), nt('Bb2'), nt('A3'), nt('D4')], 21.6, 28.9, 300, 2600, 0.46, fi=0.8, fo=0.3)
pad([nt('Bb1'), nt('F2'), nt('D3'), nt('F3')], 28.8, 31.7, 700, 1800, 0.44, fi=0.3, fo=0.2)
pad([nt('C2'), nt('G2'), nt('D3'), nt('G3'), nt('C4')], 31.6, 34.6, 700, 4200, 0.5, fi=0.2, fo=0.03)
pad([nt('D1'), nt('D2'), nt('A2'), nt('F3'), nt('E4'), nt('A4')], 35.0, DUR, 4500, 600, 0.62, fi=0.005, fo=2.4)

# baixo pulsando em colcheias, por seção
BAIXO = [(1.8, 6.75, 'D1', 0.5), (6.75, 14.3, 'Bb0', 0.8), (14.3, 21.6, 'F1', 0.75), (21.6, 28.8, 'G1', 0.7), (28.8, 31.6, 'Bb0', 0.85), (31.6, 34.6, 'C1', 1.0)]
for a, b, nota, g in BAIXO:
    f = nt(nota)
    tb = GRID0 + np.ceil((a - GRID0) / (BEAT / 2)) * BEAT / 2
    while tb < b - 0.05:
        n = int(0.24 * SR)
        t = np.arange(n) / SR
        x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) + 0.18 * saw(f * 2, n)) * env(n, 0.004, 0.09)
        acento = 1.0 if abs(((tb - GRID0) / BEAT) % 1) < 1e-6 else 0.6
        place(mus, lp(x, 900), tb, 0.22 * g * acento)
        tb += BEAT / 2

# batida suave (kick sintético) nas seções com ritmo
for a, b, g in [(6.75, 14.3, 0.8), (14.3, 21.6, 0.7), (24.1, 28.8, 0.6), (28.8, 34.6, 1.0)]:
    tb = GRID0 + np.ceil((a - GRID0) / BEAT) * BEAT
    while tb < b - 0.05:
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        f = 45 + 110 * np.exp(-t * 32)
        k = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.11)
        place(mus, k, tb, 0.34 * g)
        tb += BEAT
# chimbal fino (precisão) no Lumen e no clímax
for a, b, g in [(14.3, 21.6, 1.0), (28.8, 34.6, 1.2)]:
    tb = GRID0 + BEAT / 4 + np.ceil((a - GRID0) / (BEAT / 2)) * BEAT / 2
    while tb < b - 0.05:
        n = int(0.06 * SR)
        x = hp(noise(n), 7000) * env(n, 0.001, 0.015)
        place(mus, x, tb, 0.05 * g, pan=0.3)
        tb += BEAT / 2

# arpejos (semicolcheias)
ARP = [(6.75, 14.3, ['D4', 'F4', 'A4', 'C5', 'A4', 'F4', 'Bb4', 'F4'], 0.10, 3200),
       (14.3, 21.6, ['A4', 'C5', 'E5', 'G5', 'E5', 'C5', 'F5', 'C5'], 0.11, 5200),
       (22.4, 28.8, ['G4', 'Bb4', 'D5', 'A5', 'D5', 'Bb4', 'F5', 'D5'], 0.07, 2600),
       (28.8, 34.55, ['F4', 'Bb4', 'D5', 'F5', 'G4', 'C5', 'D5', 'G5'], 0.12, 6000)]
for a, b, notas, g, fc in ARP:
    tb = GRID0 + np.ceil((a - GRID0) / (BEAT / 4)) * BEAT / 4
    k = 0
    arp = buf()
    while tb < b - 0.03:
        f = nt(notas[k % len(notas)])
        n = int(0.2 * SR)
        t = np.arange(n) / SR
        x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t + 0.3) + 0.12 * saw(f, n)) * env(n, 0.002, 0.05)
        rampa = min(1, (tb - a) / 1.5)
        place(arp, x, tb, g * (0.55 + 0.45 * ((k % 4) == 0)) * rampa, pan=0.45 * (1 if k % 2 else -1))
        k += 1
        tb += BEAT / 4
    d = int(BEAT * 0.75 * SR)
    eco = np.zeros_like(arp)
    eco[d:] = arp[:-d] * 0.32
    place(mus, lp(arp + eco[:, ::-1], fc), 0.0)

# sinos de cristal do Nicx
for tb, nota, g in [(23.25, 'D5', 1.0), (23.9, 'A5', 0.6), (26.05, 'F5', 0.6), (26.6, 'C6', 0.7), (26.95, 'A5', 0.55), (27.6, 'E6', 0.45), (28.3, 'D6', 0.4)]:
    f = nt(nota)
    n = int(2.4 * SR)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * d) for m, a, d in [(1, 1, 1.6), (2.76, 0.32, 3.5), (5.4, 0.12, 6), (8.93, 0.05, 9)])
    place(mus, x * np.minimum(1, t / 0.004), tb, 0.07 * g, pan=float(rng.uniform(-0.5, 0.5)))

# sub contínuo
sub = np.zeros(N)
for f, a, b in [(nt('D1'), 0.5, 6.8), (nt('Bb0'), 6.75, 14.35), (nt('F1'), 14.3, 21.65), (nt('G1'), 21.6, 28.85), (nt('Bb0'), 28.8, 31.65), (nt('C1'), 31.6, 34.6), (nt('D1'), 35.0, DUR)]:
    i0, i1 = int(a * SR), int(b * SR)
    t = np.arange(i1 - i0) / SR
    sub[i0:i1] += np.sin(2 * np.pi * f * t) * np.minimum(1, t / 0.4) * np.minimum(1, (t[-1] - t) / 0.08)
place(mus, lp(sub, 110), 0.0, 0.25)

# =============================================================== SOUND DESIGN
fx = buf()


def impacto(tc, g, f0=110, f1=32, corpo=1.2, ruido=0.6, brilho=3000):
    n = int(corpo * 3 * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 9)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3 / corpo) + lp(noise(n), brilho) * np.exp(-t * 38) * ruido
    place(fx, np.tanh(x * 1.6) / 1.2, tc, g)


def whoosh(tc, w, f_lo, f_hi, g, p0=-0.8, p1=0.8):
    n = int(2 * w * SR)
    t = np.arange(n) / SR
    curve = f_lo + (f_hi - f_lo) * np.exp(-((t - w) / (w * 0.5)) ** 2)
    y = hp(sweep(noise(n)[:, None], curve)[:, 0], 120)
    e = np.exp(-((t - w) / (w * 0.42)) ** 2)
    y = y * e / (np.abs(y * e).max() + 1e-9)
    pans = np.linspace(p0, p1, n)
    place(fx, np.stack([y * np.cos((pans + 1) * np.pi / 4), y * np.sin((pans + 1) * np.pi / 4)], 1) * np.sqrt(2), tc - w, g)


def riser(t0, t1, f0, f1, g):
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    curve = f0 * (f1 / f0) ** ((t / t[-1]) ** 1.6)
    x = noise(n)
    y = np.zeros(n)
    zi = None
    for i in range(0, n, 256):
        sos = signal.butter(2, [curve[i] * 0.7, min(curve[i] * 1.4, SR * 0.45)], 'band', fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y[i:i + 256], zi = signal.sosfilt(sos, x[i:i + 256], zi=zi)
    place(fx, y * (t / t[-1]) ** 2.2 / (np.abs(y).max() + 1e-9), t0, g)


def blip(tc, f, g, pan=0.0, d=0.04):
    n = int(d * 4 * SR)
    t = np.arange(n) / SR
    place(fx, np.sin(2 * np.pi * f * t) * np.exp(-t / d * 3) * np.minimum(1, t / 0.002), tc, g, pan)


def clique(tc, g, pan=0.0):
    """Clique mecânico e preciso (Lumen)."""
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    x = bp(noise(n), 2500, 9000) * np.exp(-t * 180) + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.5
    place(fx, x, tc, g, pan)


def slam(tc, g):
    """Batida de tipografia: grave curto + metal."""
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 50 + 140 * np.exp(-t * 25)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + sum(np.sin(2 * np.pi * fr * t) * np.exp(-t * 14) * 0.08 for fr in (1630, 2470, 3710))
    x += hp(noise(n), 3000) * np.exp(-t * 60) * 0.4
    place(fx, np.tanh(x * 1.3), tc, g)


def gel(tc, dur, g, f=90, pan=0.0):
    """Massa gelatinosa: grave com vibrato e ruído filtrado que 'escorrega'."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    wob = 1 + 0.18 * np.sin(2 * np.pi * 7 * t) * np.exp(-t * 2)
    body = np.sin(2 * np.pi * np.cumsum(f * wob * (1 + 0.6 * np.exp(-t * 6))) / SR)
    sq = bp(noise(n), 250, 1100) * (0.5 + 0.5 * np.sin(2 * np.pi * 11 * t))
    e = np.minimum(1, t / 0.02) * np.exp(-t * 2.4 / dur)
    place(fx, lp(body * 0.8 + sq * 0.35, 2200) * e, tc, g, pan)


def granular(t0, t1, qtd, f_lo, f_hi, g, d=(0.005, 0.03)):
    for _ in range(qtd):
        blip(t0 + (t1 - t0) * rng.random(), float(rng.uniform(f_lo, f_hi)), g * (0.4 + rng.random()), float(rng.uniform(-1, 1)), float(rng.uniform(*d)))


def glitch(tc, dur, g):
    n = int(dur * SR)
    x = noise(n)
    hold = int(SR / 900)
    x = np.repeat(x[::hold], hold)[:n]
    x = np.round(x * 3) / 3
    place(fx, bp(x, 300, 8000) * np.minimum(1, np.arange(n) / 200) * np.exp(-np.arange(n) / SR * 8), tc, g)


# abertura
n = int(0.45 * SR)
t = np.arange(n) / SR
place(fx, np.sin(2 * np.pi * np.cumsum(180 + 1400 * (t / t[-1]) ** 2) / SR) * (t / t[-1]) ** 1.5, 0.02, 0.06)   # o ponto acende
impacto(0.45, 0.75, f0=150, f1=30, corpo=1.6, ruido=0.9, brilho=5000)
whoosh(0.75, 0.6, 300, 7000, 0.35, 0, 0)
granular(1.8, 4.6, 70, 2500, 6500, 0.02)
for tz in np.linspace(1.9, 4.4, 14):
    blip(float(tz), float(rng.choice([1760, 2093, 2349, 2637, 3136])), 0.03, float(rng.uniform(-0.7, 0.7)), 0.05)
clique(1.8, 0.12)
whoosh(2.98, 0.14, 500, 9000, 0.32, -0.9, 0.9)     # chicote
impacto(3.0, 0.18, f0=80, f1=40, corpo=0.6, ruido=0.2)
riser(4.7, 6.75, 200, 8000, 0.22)
whoosh(6.1, 0.5, 400, 8000, 0.28, 0, 0)
impacto(6.75, 0.8, f0=140, f1=30, corpo=1.8, ruido=0.9, brilho=4500)                # LOGO
riser(7.2, 8.3, 4000, 11000, 0.03)
for tc in (8.55, 9.15, 9.75):
    slam(tc, 0.5)
glitch(10.68, 0.18, 0.25)
granular(10.75, 12.0, 60, 1200, 4000, 0.025, (0.01, 0.04))
for i in range(30):
    clique(12.05 + 0.42 * rng.random(), 0.06, float(rng.uniform(-0.8, 0.8)))        # fragmentos encaixam
riser(12.6, 13.3, 2000, 7000, 0.05)
whoosh(14.1, 0.45, 300, 9000, 0.4, 0, 0)
impacto(14.3, 0.35, f0=90, f1=38, corpo=0.8, ruido=0.4)
# Lumen: preciso, digital, mecânico
n = int(0.7 * SR)
t = np.arange(n) / SR
y = hp(sweep(noise(n)[:, None], 9000 * (600 / 9000) ** (t / t[-1]))[:, 0], 500) * np.exp(-t * 3)
place(fx, y / np.abs(y).max(), 14.3, 0.12)
for i in range(18):
    clique(14.45 + i * 0.025, 0.03, -0.6)
slam(15.25, 0.45)
for tc in (16.6, 17.4, 18.2, 19.5):
    clique(tc, 0.16)
    impacto(tc, 0.12, f0=70, f1=40, corpo=0.4, ruido=0.15)
for i in range(4):
    whoosh(17.45 + i * 0.07, 0.12, 400, 5000, 0.08, 0.8, -0.2)
for i in range(8):
    blip(18.3 + i * 0.05, 3520 + 220 * i, 0.04, -0.8 + i * 0.22, 0.03)
for tc in (19.7, 20.02, 20.34):
    slam(tc, 0.3)
granular(21.2, 21.6, 80, 2000, 8000, 0.03, (0.004, 0.012))
# Nicx: orgânico + eletrônico
whoosh(21.95, 0.4, 300, 8000, 0.45, -1, 1)                 # rajada atravessa a tela
n = int(1.1 * SR)
t = np.arange(n) / SR
orb = bp(noise(n), 600, 2600) * (0.6 + 0.4 * np.sin(2 * np.pi * 6 * t))
pans = np.sin(2 * np.pi * 1.6 * t)
place(fx, np.stack([orb * np.cos((pans + 1) * np.pi / 4), orb * np.sin((pans + 1) * np.pi / 4)], 1) * np.exp(-((t - 0.55) / 0.5) ** 2)[:, None], 22.4, 0.12)
riser(22.6, 23.25, 150, 2500, 0.12)
gel(23.25, 1.4, 0.55, 75)                                  # o gel nasce
impacto(23.25, 0.25, f0=60, f1=32, corpo=1.2, ruido=0.05)
whoosh(24.6, 0.55, 150, 2500, 0.25, -0.7, 0.7)
gel(24.2, 0.9, 0.3, 110, -0.4)                             # perseguição
gel(24.8, 0.7, 0.25, 95, 0.4)
impacto(25.15, 0.3, f0=200, f1=60, corpo=0.4, ruido=0.6, brilho=7000)   # divide
granular(25.15, 25.6, 60, 3000, 8000, 0.03, (0.005, 0.02))
n = int(0.5 * SR)
t = np.arange(n) / SR
rev = bp(noise(n), 400, 3000) * (t / t[-1]) ** 3
place(fx, rev / np.abs(rev).max(), 25.5, 0.12)
gel(26.0, 0.8, 0.4, 85)                                    # recompõe
for tr in (26.6, 26.95):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    place(fx, np.sin(2 * np.pi * (520 + 140 * np.exp(-t * 5)) * t) * np.exp(-t * 3.2) * np.minimum(1, t / 0.003), tr, 0.05)
for i in range(6):
    gel(26.2 + i * 0.35, 0.25, 0.06, 160 + 30 * i, float(rng.uniform(-0.5, 0.5)))  # curiosidade: bolhas sutis
# duas iniciativas
whoosh(28.8, 0.3, 500, 9000, 0.3, -0.2, 0.2)
impacto(28.8, 0.3, f0=90, f1=36, corpo=0.8, ruido=0.3)
riser(31.6, 34.6, 120, 10000, 0.3)
n = int(3.0 * SR)
t = np.arange(n) / SR
suc = bp(noise(n), 200, 1500) * (t / t[-1]) ** 2
place(fx, suc / np.abs(suc).max(), 31.6, 0.12)
# silêncio de 34,6 a 35,0; prato invertido curto e o impacto final
n = int(0.4 * SR)
t = np.arange(n) / SR
rc = hp(noise(n), 5000) * np.exp(-(t[::-1]) * 6)
place(fx, rc / np.abs(rc).max(), 35.0 - 0.4, 0.06)
impacto(35.0, 0.95, f0=150, f1=28, corpo=2.4, ruido=1.0, brilho=5000)
impacto(35.0, 0.3, f0=240, f1=90, corpo=0.5, ruido=0.2, brilho=7000)
riser(35.15, 36.6, 6000, 12000, 0.02)

mus_mix = mus + reverb(mus) * 0.3
fx_mix = fx + reverb(fx) * 0.35
# silêncio dramático antes da assinatura
gate = np.ones(N)
a, b = int(34.6 * SR), int(35.0 * SR)
gate[a - 2400:a] = np.linspace(1, 0, 2400) ** 2
gate[a:b] = 0
mus_mix *= gate[:, None]
fx_mix *= np.maximum(gate, (T >= 34.55) & (T < 35.0))[:, None]  # o prato invertido atravessa o silêncio

# =============================================================== NARRAÇÃO
voz = buf()
for fala in LINHA['falas']:
    x, sr = sf.read(os.path.join(RAIZ, 'public', 'voz', fala['arq']))
    x = x if x.ndim == 1 else x.mean(1)
    if sr != SR:
        x = signal.resample_poly(x, SR, sr)
    place(voz, x, fala['t'])
v = hp(voz, 70)
b_, a_ = signal.iirpeak(3200, 2.5, fs=SR)
v = v + signal.lfilter(b_, a_, v, axis=0) * (10 ** (1.5 / 20) - 1)
envv = np.sqrt(signal.lfilter([1 - 0.999], [1, -0.999], (v ** 2).mean(1)) + 1e-9)
v = v * np.minimum(1, (0.09 / envv) ** 0.35)[:, None]
v = v / np.abs(v).max() * 0.5
v = v + reverb(v, IR_SALA) * 0.05 + reverb(v) * 0.03

venv = signal.lfilter([1 - 0.9995], [1, -0.9995], np.abs(v).mean(1))
duck = 1 - 0.42 * np.clip(venv / (venv.max() * 0.25), 0, 1)
cama = mus_mix * 0.55 + fx_mix * 0.85


def master(x):
    x = hp(x, 22)
    peak = np.abs(x).max(1)
    pk = np.maximum.reduce([np.roll(peak, -i) for i in range(0, int(0.004 * SR), 16)])
    g = signal.lfilter([1 - 0.995], [1, -0.995], np.minimum(1, 0.89 / (pk + 1e-9)))
    y = x * np.minimum(g, 0.89 / (peak + 1e-9))[:, None]
    fo = int(0.6 * SR)
    y[-fo:] *= (np.linspace(1, 0, fo) ** 1.5)[:, None]
    return y


out = os.path.join(RAIZ, 'public', 'audio')
os.makedirs(out, exist_ok=True)
mix = master((cama * duck[:, None] + v) / np.abs(cama * duck[:, None] + v).max() * 1.5)
sf.write(os.path.join(out, 'mix_final.wav'), mix.astype(np.float32), SR, subtype='PCM_24')
sf.write(os.path.join(out, 'mix_sem_narracao.wav'), master(cama / np.abs(cama).max() * 1.3).astype(np.float32), SR, subtype='PCM_24')
rms = 20 * np.log10(np.sqrt((mix ** 2).mean()))
print(f'RMS {rms:.1f} dBFS, pico {20 * np.log10(np.abs(mix).max()):.2f} dBFS')

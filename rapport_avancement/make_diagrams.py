# -*- coding: utf-8 -*-
"""Génère les diagrammes de séquence (matplotlib) et les emplacements de
captures d'écran (Pillow) pour le rapport AgentFlow."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")
os.makedirs(IMG, exist_ok=True)

PRIMARY = "#1D4ED8"
INK     = "#0F1B2D"
SOFT    = "#64748B"
BOXBG   = "#EFF6FF"
GRID    = "#CBD5E1"


def draw_sequence(path, actors, messages):
    """actors: list[str] ; messages: list[(frm, to, text, is_return)]"""
    n = len(actors)
    xs = [1.8 + i * 3.4 for i in range(n)]
    width = xs[-1] + 1.8

    # hauteur : une ligne par message (les self prennent un peu plus)
    row_h = 0.95
    y = 2.2
    ys = []
    for (frm, to, _t, _r) in messages:
        ys.append(y)
        y += row_h * (1.35 if frm == to else 1.0)
    total_h = y + 0.6

    fig, ax = plt.subplots(figsize=(width * 0.52, total_h * 0.52), dpi=150)
    ax.set_xlim(0, width)
    ax.set_ylim(0, total_h)
    ax.axis("off")
    ax.invert_yaxis()

    # entêtes acteurs + lignes de vie
    bw, bh, y_head = 2.7, 0.8, 0.9
    for i, a in enumerate(actors):
        ax.add_patch(FancyBboxPatch(
            (xs[i] - bw / 2, y_head - bh / 2), bw, bh,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            fc=BOXBG, ec=PRIMARY, lw=1.4, zorder=3))
        ax.text(xs[i], y_head, a, ha="center", va="center",
                fontsize=8.6, color=INK, weight="bold", zorder=4)
        ax.plot([xs[i], xs[i]], [y_head + bh / 2, total_h - 0.3],
                ls=(0, (4, 3)), color=GRID, lw=1, zorder=1)

    # messages
    for (frm, to, text, ret), yy in zip(messages, ys):
        col = SOFT if ret else INK
        if frm == to:  # message réflexif
            x0 = xs[frm]
            ax.plot([x0, x0 + 1.0], [yy, yy], color=col, lw=1.1, zorder=2)
            ax.plot([x0 + 1.0, x0 + 1.0], [yy, yy + 0.34], color=col, lw=1.1, zorder=2)
            ax.annotate("", xy=(x0, yy + 0.34), xytext=(x0 + 1.0, yy + 0.34),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1), zorder=2)
            ax.text(x0 + 1.2, yy + 0.17, text, ha="left", va="center",
                    fontsize=7.3, color=col)
        else:
            ax.annotate("", xy=(xs[to], yy), xytext=(xs[frm], yy),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=1.15,
                                        linestyle="--" if ret else "-"), zorder=2)
            ax.text((xs[frm] + xs[to]) / 2, yy - 0.16, text, ha="center",
                    va="bottom", fontsize=7.3, color=col)

    fig.savefig(path, bbox_inches="tight", facecolor="white", pad_inches=0.12)
    plt.close(fig)
    print("diagramme:", os.path.basename(path))


# ── 1. Création d'un espace RAG ──
draw_sequence(os.path.join(IMG, "seq_creation.png"),
    ["IT", "Frontend", "API (Backend)", "PostgreSQL"],
    [
        (0, 1, "Remplit le formulaire\n(nom, config, visibilité)", False),
        (1, 2, "POST /rag/spaces", False),
        (2, 2, "Vérifie rôle & permissions", False),
        (2, 3, "INSERT RAGSpace\n(propriétaire, privé, DRAFT)", False),
        (2, 3, "INSERT accès / collaborateurs", False),
        (3, 2, "OK", True),
        (2, 1, "Espace créé (JSON)", True),
        (1, 0, "Affiche l'espace (Brouillon)", True),
    ])

# ── 2. Exécution du système RAG ──
draw_sequence(os.path.join(IMG, "seq_execution.png"),
    ["Utilisateur", "Frontend", "API", "Embedding", "pgvector", "LLM"],
    [
        (0, 1, "Pose une question", False),
        (1, 2, "POST /query", False),
        (2, 2, "Contrôle d'accès", False),
        (2, 3, "Vectorise la question", False),
        (3, 2, "vecteur", True),
        (2, 4, "Recherche hybride (top-k)", False),
        (4, 2, "chunks pertinents", True),
        (2, 5, "Prompt (question + contexte)", False),
        (5, 2, "Réponse générée", True),
        (2, 1, "Réponse + sources", True),
        (1, 0, "Affiche réponse & sources", True),
    ])

# ── 3. Gestion des clés API ──
draw_sequence(os.path.join(IMG, "seq_apikey.png"),
    ["Admin / IT", "Frontend", "API", "Chiffrement", "PostgreSQL"],
    [
        (0, 1, "Saisit une clé API (fournisseur)", False),
        (1, 2, "Enregistre la clé", False),
        (2, 3, "encrypt_key(clé)", False),
        (3, 2, "clé chiffrée", True),
        (2, 4, "Stocke api_key_enc", False),
        (4, 2, "OK", True),
        (2, 1, "Confirmation (jamais en clair)", True),
        (2, 4, "À l'usage : lit api_key_enc", False),
        (2, 3, "decrypt_key → appel du modèle", False),
    ])


# ── Emplacements de captures d'écran ──
def placeholder(name, caption, w=1200, h=680):
    img = Image.new("RGB", (w, h), "#F1F5F9")
    d = ImageDraw.Draw(img)
    for off, col in ((0, "#CBD5E1"),):
        d.rectangle([6 + off, 6 + off, w - 6 - off, h - 6 - off], outline=col, width=3)
    try:
        f1 = ImageFont.truetype("arialbd.ttf", 40)
        f2 = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        f1 = ImageFont.load_default()
        f2 = f1
    d.text((w / 2, h / 2 - 34), "CAPTURE D'ÉCRAN À INSÉRER", fill="#475569",
           anchor="mm", font=f1)
    d.text((w / 2, h / 2 + 34), caption, fill="#64748B", anchor="mm", font=f2)
    img.save(os.path.join(IMG, name))
    print("capture (placeholder):", name)


placeholder("shot_extraction.png", "Étape 1 — Extraction : texte chargé du document")
placeholder("shot_parsed.png",     "Étape 1 — Document parsé (sections, tableaux, images)")
placeholder("shot_chunking.png",   "Étape 2 — Page de configuration du découpage (chunking)")
placeholder("shot_embedding.png",  "Étape 3 — Page de configuration de l'embedding")
placeholder("shot_llm.png",        "Étape 6 — Choix du modèle LLM")

print("OK — images générées dans", IMG)

# -*- coding: utf-8 -*-
"""Génère le rapport d'avancement AgentFlow en PDF (mise en page soignée)."""
import os
from fpdf import FPDF, FontFace
from PIL import Image as _PILImage

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

PRIMARY = (29, 78, 216)
INK     = (15, 27, 45)
SOFT    = (100, 116, 139)
LINE    = (203, 213, 225)
OK      = (4, 120, 87)
WIP     = (180, 83, 9)
PLAN    = (107, 114, 128)

CW = 170  # largeur de contenu (mm)

# Caractères hors Windows-1252 → équivalents sûrs
REPL = {"→": "->", "≈": "~", " ": " ", " ": " ", "•": "-"}


def s(txt):
    for k, v in REPL.items():
        txt = txt.replace(k, v)
    return txt.encode("cp1252", "replace").decode("cp1252")


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(10)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*SOFT)
        self.cell(0, 5, s("AgentFlow — Rapport d'avancement"), align="L")
        self.cell(0, 5, "Fadi Khala", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(20, 17, 190, 17)
        self.set_y(22)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*SOFT)
        self.cell(0, 6, str(self.page_no()), align="C")


pdf = PDF(format="A4")
pdf.core_fonts_encoding = "cp1252"   # typographie française complète
pdf.set_margins(20, 20, 20)
pdf.set_auto_page_break(True, margin=18)
pdf.add_page()

_SEC = [0]


def section(title):
    _SEC[0] += 1
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.multi_cell(CW, 7, s(f"{_SEC[0]}.  {title}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def sub(title):
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*INK)
    pdf.multi_cell(CW, 5.5, s(title), new_x="LMARGIN", new_y="NEXT")


def para(txt):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 48, 60)
    pdf.multi_cell(CW, 5.2, s(txt), align="J", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def bullets(items, ordered=False):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 48, 60)
    for i, it in enumerate(items):
        marker = f"{i+1}." if ordered else "-"
        x0 = pdf.get_x()
        pdf.cell(6, 5.2, marker)
        pdf.set_x(x0 + 6)
        pdf.multi_cell(CW - 6, 5.2, s(it), align="J", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def simple_table(rows, widths, header=True, state_col=None):
    pdf.set_font("Helvetica", "", 9.3)
    head_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=PRIMARY)
    with pdf.table(
        width=CW, col_widths=widths, text_align="LEFT", line_height=5.4,
        headings_style=head_style, first_row_as_headings=header,
        borders_layout="SINGLE_TOP_LINE",
    ) as table:
        for r_i, data_row in enumerate(rows):
            row = table.row()
            for c_i, datum in enumerate(data_row):
                if state_col is not None and r_i > 0 and c_i == state_col:
                    color = OK if "Termin" in datum else WIP if "cours" in datum else PLAN
                    row.cell(s(datum), style=FontFace(emphasis="BOLD", color=color))
                else:
                    row.cell(s(datum))
    pdf.ln(2)


def figure(path, w_mm, caption=None):
    iw, ih = _PILImage.open(path).size
    h_mm = w_mm * ih / iw
    need = h_mm + (8 if caption else 3)
    if pdf.get_y() + need > pdf.h - pdf.b_margin:
        pdf.add_page()
    pdf.image(path, x=(210 - w_mm) / 2, w=w_mm)
    if caption:
        pdf.ln(1.2)
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*SOFT)
        pdf.multi_cell(CW, 4.5, s(caption), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2.5)


# ══════════════════════════════════════════════════════
# EN-TÊTE DU RAPPORT (page 1)
# ══════════════════════════════════════════════════════
pdf.set_font("Helvetica", "", 8.5)
pdf.set_text_color(*SOFT)
pdf.cell(0, 5, s("RAPPORT D'AVANCEMENT DE PROJET"), align="C",
         new_x="LMARGIN", new_y="NEXT")
pdf.ln(1)
pdf.set_font("Helvetica", "B", 24)
pdf.set_text_color(*INK)
pdf.cell(0, 11, "AgentFlow", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 12.5)
pdf.set_text_color(*PRIMARY)
pdf.cell(0, 7, s("Plateforme de création et de déploiement d'agents RAG"),
         align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)
pdf.set_draw_color(*LINE)
pdf.line(20, pdf.get_y(), 190, pdf.get_y())
pdf.ln(4)

pdf.set_font("Helvetica", "", 9.5)
pdf.set_text_color(*SOFT)
pdf.cell(CW / 2, 5, s("Étudiant : Fadi Khala"))
pdf.cell(CW / 2, 5, "Encadrant : Pr. Omri", align="R", new_x="LMARGIN", new_y="NEXT")
pdf.cell(CW / 2, 5, "Projet : AgentFlow")
pdf.cell(CW / 2, 5, "Date : 13 juillet 2026", align="R", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)

# ── 1. Introduction ──
section("Introduction et contexte")
para("Ce document présente l'état d'avancement du projet AgentFlow, une "
     "plateforme web permettant à une organisation de construire, configurer, "
     "déployer et exploiter des agents conversationnels basés sur la technologie "
     "RAG (Retrieval-Augmented Generation), à partir de ses propres documents "
     "internes et sans écrire de code.")
para("L'idée centrale est de séparer clairement trois rôles au sein d'une même "
     "organisation :")
bullets([
    "l'Administrateur, qui gère l'organisation, les départements, les "
    "utilisateurs et les fournisseurs de modèles (clés API) ;",
    "l'ingénieur IT, qui construit et règle finement les pipelines RAG, les "
    "teste, puis les déploie ;",
    "l'utilisateur final (end-user), qui interroge en langage naturel les agents "
    "mis à sa disposition et consulte les documents sources.",
])
para("La plateforme est multi-organisation et cloisonnée par département "
     "(ex. RH, Finance, Juridique), chaque département disposant de ses propres "
     "espaces documentaires et de ses propres agents.")

# ── 2. Objectifs ──
section("Objectifs du projet")
para("Objectif général. Offrir un outil « no-code » complet qui rend accessible "
     "la mise en place d'un système RAG de qualité professionnelle, tout en "
     "laissant à l'ingénieur IT le contrôle fin de chaque étape du pipeline.")
sub("Objectifs spécifiques")
bullets([
    "Prendre en charge de multiples sources et formats de documents "
    "(PDF, DOCX, PPTX, CSV, XLSX, HTML, pages web, Google Drive).",
    "Rendre chaque étape du pipeline configurable : découpage (chunking), "
    "vectorisation (embedding), recherche et génération.",
    "Permettre l'itération : tester plusieurs configurations, les sauvegarder en "
    "versions, puis déployer la meilleure.",
    "Gérer finement les permissions (propriétaire, collaborateurs IT, accès des "
    "utilisateurs finaux) et la confidentialité des espaces.",
    "Fournir une expérience utilisateur soignée pour la consultation des agents "
    "et des documents.",
])

# ── 3. Méthodologie ──
section("Méthodologie et organisation du travail")
para("Le développement suit une démarche itérative et incrémentale, organisée "
     "par lots fonctionnels. Chaque itération livre une fonctionnalité complète "
     "et testée de bout en bout : conception, implémentation côté backend "
     "(services et modèles), implémentation côté frontend (React), puis "
     "vérification sur une base de données réelle.")
bullets([
    "Versionnement du code avec Git et suivi continu des évolutions.",
    "Migrations de schéma légères et idempotentes, exécutées au démarrage, pour "
    "faire évoluer la base sans rupture ni outil externe.",
    "Tests de fumée systématiques à chaque étape (permissions, cycle de "
    "déploiement, accès) sur la base PostgreSQL du projet.",
    "Principe directeur : expérience « no-code » pour l'utilisateur final, "
    "contrôle complet pour l'ingénieur IT.",
])

# ── 4. Architecture ──
section("Architecture technique")
para("Le projet suit une architecture en couches, avec une séparation nette "
     "entre les routes HTTP, la logique métier (services) et les modèles de "
     "données.")
simple_table([
    ["Couche", "Technologies et rôle"],
    ["Frontend", "React + Vite — interfaces distinctes par rôle (Admin, IT, "
                 "End-user), design responsive."],
    ["Backend", "FastAPI (Python) — API REST, authentification par jeton, "
                "contrôle d'accès par rôle."],
    ["Base de données", "PostgreSQL + extension pgvector pour le stockage et la "
                        "recherche vectorielle."],
    ["Fournisseurs", "Groq, OpenAI, Ollama (LLM), BGE-M3 / Cohere (embeddings), "
                     "Docling (parsing), Crawl4AI (web), Google Drive."],
], widths=(30, 70))
para("La couche « fournisseurs » est entièrement modulaire : chaque famille "
     "(chargeurs, parseurs, nettoyeurs, découpage, embedding, LLM) est isolée "
     "derrière une factory qui résout dynamiquement le fournisseur et le modèle à "
     "partir de la configuration de l'espace.")

# ── 5. Modèle de données ──
section("Modèle de données")
para("Les principales entités de la base reflètent directement le domaine "
     "métier :")
simple_table([
    ["Entité", "Rôle"],
    ["Organisation / Département / Utilisateur",
     "Structure multi-organisation et rôles (Admin, IT, End-user)."],
    ["RAGSpace", "Espace RAG : configuration complète du pipeline, statut, "
     "propriétaire et visibilité."],
    ["RAGSpaceVersion", "Instantané (snapshot) d'une configuration ; support du "
     "versioning et du déploiement."],
    ["RAGSpaceCollaborator", "IT co-constructeurs autorisés par le propriétaire."],
    ["RAGSpaceAccess", "Liste des utilisateurs finaux autorisés à interroger un "
     "espace publié."],
    ["Document", "Fichier source et son cycle de vie : UPLOADING -> LOADED -> "
     "EXTRACTED -> INDEXED."],
    ["Chunk", "Fragment de texte vectorisé, stocké dans pgvector avec ses "
     "métadonnées."],
], widths=(40, 60))

# ── Conception ──
section("Conception")
para("Cette section illustre, à l'aide de diagrammes de séquence, les principaux "
     "scénarios d'interaction entre l'utilisateur, l'interface, l'API, la base de "
     "données et les modèles.")
sub("Création d'un espace RAG")
para("L'ingénieur IT renseigne la configuration ; l'API vérifie ses droits, crée "
     "l'espace (propriétaire, visibilité, statut Brouillon) et enregistre les "
     "règles d'accès.")
figure(os.path.join(IMG, "seq_creation.png"), 150,
       "Diagramme de séquence — Création d'un espace RAG")
sub("Exécution du système RAG")
para("À chaque question, l'API contrôle l'accès, vectorise la requête, effectue "
     "une recherche hybride dans pgvector, puis fait générer la réponse par le "
     "LLM avec les passages retrouvés comme contexte.")
figure(os.path.join(IMG, "seq_execution.png"), 168,
       "Diagramme de séquence — Exécution du système RAG")
sub("Gestion des clés API")
para("Les clés fournisseurs ne sont jamais stockées en clair : elles sont "
     "chiffrées avant enregistrement, puis déchiffrées uniquement au moment de "
     "l'appel au modèle.")
figure(os.path.join(IMG, "seq_apikey.png"), 150,
       "Diagramme de séquence — Gestion des clés API")

# ── 6. Pipeline ──
section("Le pipeline RAG (cœur du projet)")
para("Chaque document parcourt un pipeline complet, dont chaque étape est "
     "visualisable et paramétrable par l'ingénieur IT :")
simple_table([
    ["Étape", "Description"],
    ["1. Ingestion", "Import de fichiers, Google Drive, scraping d'URL, crawl de "
                     "site, sitemap, flux RSS."],
    ["2. Chargement", "Extraction du texte brut et de la structure (Docling pour "
                      "les PDF/DOCX/PPTX)."],
    ["3. Nettoyage", "Correction OCR, dé-duplication, masquage des données "
                     "personnelles (PII)."],
    ["4. Parsing", "Structuration en sections, tableaux et images ; résumé des "
                   "images pour les rendre indexables."],
    ["5. Découpage", "Stratégies de chunking adaptées à chaque format (récursif, "
                     "par page, par ligne, sémantique, hiérarchique)."],
    ["6. Vectorisation", "Calcul des embeddings (BGE-M3 local par défaut, ou "
                         "fournisseur externe)."],
    ["7. Indexation", "Stockage des vecteurs dans pgvector."],
    ["8. Recherche", "Recherche hybride (sémantique + mots-clés) avec pondération "
                     "réglable."],
    ["9. Génération", "Réponse produite par le LLM configuré, avec citation des "
                      "sources et prompt système personnalisable."],
], widths=(24, 76))
para("L'ingénieur peut prévisualiser le résultat de chaque étape (texte chargé, "
     "contenu parsé, chunks générés) et même éditer manuellement le contenu "
     "extrait avant l'indexation.")

# ── Travail réalisé ──
section("Travail réalisé")
para("Cette section présente, captures à l'appui, les étapes clés effectivement "
     "réalisées de la chaîne de traitement.")
sub("Étape 1 : Extraction de documents")
para("Le document importé est d'abord chargé (texte brut), puis parsé en une "
     "structure riche : titres, sections, tableaux et images. Le contenu extrait "
     "est prévisualisable et éditable avant l'indexation.")
figure(os.path.join(IMG, "shot_extraction.png"), 150,
       "Étape 1 — Extraction : texte chargé du document")
figure(os.path.join(IMG, "shot_parsed.png"), 150,
       "Étape 1 — Document parsé (sections, tableaux, images)")
sub("Étape 2 : Chunking (découpage)")
para("Le contenu est découpé en fragments (chunks) selon une stratégie adaptée "
     "au format du document, avec des paramètres réglables (taille, "
     "chevauchement, stratégie par format).")
figure(os.path.join(IMG, "shot_chunking.png"), 150,
       "Étape 2 — Page de configuration du découpage")
sub("Étape 3 : Embedding (vectorisation)")
para("Chaque fragment est transformé en vecteur numérique par un modèle "
     "d'embedding (BGE-M3 local par défaut, ou un fournisseur externe).")
figure(os.path.join(IMG, "shot_embedding.png"), 150,
       "Étape 3 — Page de configuration de l'embedding")
sub("Étape 4 : Stockage vectoriel")
para("Les vecteurs et leurs métadonnées sont stockés dans PostgreSQL via "
     "l'extension pgvector, avec un index dédié permettant une recherche par "
     "similarité efficace.")
sub("Étape 5 : Recherche hybride")
para("À l'interrogation, le système combine une recherche sémantique (vecteurs) "
     "et une recherche par mots-clés, avec une pondération réglable, afin de "
     "sélectionner les passages les plus pertinents (top-k).")
sub("Étape 6 : Génération LLM")
para("Les passages retrouvés sont fournis comme contexte au modèle de langage "
     "choisi, qui rédige une réponse en citant ses sources. Le fournisseur, le "
     "modèle et le prompt système sont configurables.")
figure(os.path.join(IMG, "shot_llm.png"), 150,
       "Étape 6 — Choix du modèle LLM")

# ── 7. Fonctionnalités réalisées ──
section("Fonctionnalités réalisées")
sub("Gestion des accès et des rôles")
para("Organisations, départements et utilisateurs avec les rôles Admin / IT / "
     "End-user ; relation plusieurs-à-plusieurs entre utilisateurs et "
     "départements ; authentification et invitations.")
sub("Espaces RAG entièrement configurables")
para("Création d'un espace rattaché à un département, avec le réglage fin de "
     "toutes les étapes du pipeline. Chaque IT peut utiliser les fournisseurs de "
     "l'entreprise ou ses propres clés (chiffrées au repos).")
sub("Versioning des configurations et cycle de déploiement")
para("C'est l'un des apports majeurs de la dernière phase :")
bullets([
    "l'IT peut sauvegarder plusieurs versions d'une configuration (v1, v2…), "
    "chacune capturant l'ensemble des paramètres du pipeline ;",
    "il peut recharger une version dans l'éditeur pour la comparer ;",
    "il choisit ensuite la version à déployer auprès des utilisateurs finaux.",
])
para("Un cycle de vie clair encadre l'espace : Brouillon -> Déployé -> En "
     "édition. L'IT peut « mettre en pause » un agent déployé pour ajouter des "
     "documents ou modifier la configuration, puis le re-déployer ; pendant ce "
     "temps, l'utilisateur final voit l'agent avec la mention « en mise à jour ».")
sub("Détection intelligente de ré-indexation")
para("Le système distingue les paramètres qui impactent réellement l'index "
     "(découpage, embedding) de ceux qui n'agissent qu'au moment de la requête "
     "(LLM, température, prompt). Une ré-indexation n'est demandée que lorsque la "
     "configuration d'indexation change effectivement — l'ajout d'un simple "
     "document n'indexe que ce document, sans reconstruire tout l'index.")
sub("Modèle de permissions à deux niveaux")
bullets([
    "Propriétaire : l'IT créateur de l'espace. Seul à pouvoir déployer, publier, "
    "importer et supprimer des documents.",
    "Collaborateurs IT : co-constructeurs invités par le propriétaire ; ils "
    "peuvent régler la configuration, créer des versions et tester, mais pas "
    "déployer ni gérer les documents.",
    "Espace privé : par défaut, un espace n'est visible que de son propriétaire "
    "et de son équipe IT — aucun utilisateur final n'y accède tant qu'il n'est "
    "pas explicitement publié.",
])
sub("Expérience utilisateur final")
para("Interface repensée : liste des agents déployés, conversation en langage "
     "naturel avec citation des sources, et panneau « Documents » permettant "
     "d'ouvrir et de consulter les PDF originaux en ligne (visionneuse intégrée).")
sub("Prévisualisation IT des agents déployés")
para("Une vue dédiée permet à l'IT de tester un agent déployé exactement comme "
     "le voit l'utilisateur final (même chat, mêmes documents), via un menu "
     "« RAG Spaces » à deux entrées : Espace de travail et Agents déployés.")

# ── 8. Synthèse ──
section("Synthèse de l'avancement")
simple_table([
    ["Module", "État", "Avanc."],
    ["Gestion des utilisateurs / départements / rôles", "Terminé", "100%"],
    ["Ingestion multi-source et multi-format", "Terminé", "100%"],
    ["Chargement / parsing / nettoyage des documents", "Terminé", "95%"],
    ["Découpage (chunking) par format", "Terminé", "95%"],
    ["Embeddings et indexation (pgvector)", "Terminé", "100%"],
    ["Recherche hybride et génération (LLM factory)", "Terminé", "95%"],
    ["Versioning et cycle de déploiement", "Terminé", "90%"],
    ["Permissions (propriétaire / équipe / accès)", "Terminé", "90%"],
    ["Expérience utilisateur final (chat + documents)", "Terminé", "85%"],
    ["Module d'évaluation (comparaison des versions)", "Planifié", "10%"],
    ["Auto-tuning / découpage agentique", "Planifié", "0%"],
    ["Workflows, API Agent, Data Agent", "En cours", "30%"],
], widths=(64, 22, 14), state_col=1)
para("Avancement global estimé : environ 80 %. Le cœur fonctionnel (pipeline RAG "
     "complet, configuration, versioning, déploiement, permissions et "
     "consommation par l'utilisateur final) est opérationnel et testé de bout en "
     "bout.")

# ── 9. Difficultés ──
section("Difficultés rencontrées et solutions")
bullets([
    "Cohérence configuration / index. Un changement de découpage ou d'embedding "
    "rend l'index existant obsolète. Solution : un indicateur de ré-indexation "
    "calculé par empreinte des seuls paramètres d'indexation, pour n'alerter "
    "qu'en cas de changement réel.",
    "Permissions multi-couches. Concilier propriétaire, collaborateurs IT et "
    "accès des utilisateurs finaux sur un même point d'entrée de listing. "
    "Solution : un filtrage par rôle centralisé dans la couche service.",
    "Migrations de schéma sans Alembic. Solution : des migrations légères et "
    "idempotentes exécutées au démarrage (ADD COLUMN IF NOT EXISTS, conversion "
    "de types).",
    "Consultation de fichiers protégés en cross-origin. Solution : récupération "
    "du fichier en blob authentifié côté client avant affichage dans la "
    "visionneuse.",
])

# ── 10. Prochaines étapes ──
section("Prochaines étapes")
bullets([
    "Module d'évaluation : jeu de test et métriques (taux de réponse pertinente, "
    "MRR) pour comparer objectivement les versions et guider le choix de "
    "déploiement.",
    "Auto-tuning : sélection automatique de la stratégie de découpage la mieux "
    "adaptée à chaque document.",
    "Workflows et agents avancés (API Agent, Data Agent).",
    "Historique de conversation côté utilisateur final.",
    "Tests, sécurité et préparation au déploiement en production.",
], ordered=True)
para("Le calendrier prévisionnel se décline en trois horizons :")
simple_table([
    ["Échéance", "Objectif principal"],
    ["Court terme", "Module d'évaluation : métriques et comparaison objective des "
     "versions d'un espace."],
    ["Moyen terme", "Auto-tuning du découpage ; workflows et agents avancés "
     "(API Agent, Data Agent)."],
    ["Long terme", "Tests approfondis, sécurité et mise en production."],
], widths=(24, 76))

# ── 11. Conclusion ──
section("Conclusion")
para("Le projet AgentFlow a atteint un stade avancé et fonctionnel : l'ensemble "
     "de la chaîne RAG — de l'ingestion des documents jusqu'à la réponse citée à "
     "l'utilisateur final — est en place, avec une gestion complète des "
     "configurations, des versions, du déploiement et des permissions. Les "
     "prochaines étapes se concentreront sur l'évaluation quantitative des "
     "configurations et sur les fonctionnalités avancées, afin de consolider la "
     "qualité et de préparer une mise en production. Je reste à votre disposition "
     "pour en discuter plus en détail lors de la réunion.")

out = __file__.replace("generate_pdf.py", "rapport_avancement.pdf")
pdf.output(out)
print("PDF genere :", out, "-", pdf.page_no(), "pages")

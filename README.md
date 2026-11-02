# 🥕 Quitoque

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5.svg?style=flat-square&logo=homeassistant)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz/)
[![Maintainers](https://img.shields.io/badge/maintainers-%40AuroreVgn%20%7C%20%40Li0c0-007ec6?style=flat-square)](https://github.com/Li0c0)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?style=flat-square&logo=ko-fi)](https://ko-fi.com/aurorevgn)

## 🏠 Mes projets Home Assistant

Retrouvez l'ensemble de mes intégrations et projets Home Assistant sur ma page dédiée : [**🏠 Découvrir mes projets Home Assistant**](https://erra.me)

## ☕ Soutenir le projet

Si cette intégration vous est utile et que vous souhaitez soutenir son développement et sa maintenance :

<p>
  <a href="https://ko-fi.com/aurorevgn">
    <img src="https://storage.ko-fi.com/cdn/kofi4.png?v=3"
         alt="Support me on Ko-fi"
         height="45">
  </a>
</p>

## 📑 Sommaire

- [⚠️ Important](#toc-section-1)
- [✨ Fonctionnalités](#toc-section-2)
- [🛡️ Compatibilité](#toc-section-3)
- [📦 Installation](#toc-section-4)
- [⚙️ Configuration](#toc-section-5)
- [📊 Entités créées](#toc-section-6)
- [📈 Dashboard Quitoque](#toc-section-7)
- [🧩 Carte Lovelace — Quitoque Card](#toc-section-8)
- [📅 Calendrier](#toc-section-9)
- [📅 Utilisation avec Google Calendar](#toc-section-10)
- [📄 PDF des recettes](#toc-section-11)
- [🥕 Recettes et produits du Marché](#toc-section-12)
- [🎛️ Options](#toc-section-13)
- [🔧 Services Home Assistant](#toc-section-14)
- [🛠️ Dépannage](#toc-section-15)
- [🤝 Contributions et problèmes](#toc-section-16)
- [📄 Licence](#toc-section-17)

<a name="toc-section-1"></a>

<a name="toc-section-1"></a>

## ⚠️ Important
Intégration personnalisée **Home Assistant** permettant de récupérer les prochaines recettes d'un compte **Quitoque**, de suivre les livraisons de **S0 à S+4**, de les ajouter à un calendrier Home Assistant (ou Google), de générer les fiches recettes en PDF et d'afficher les informations dans un **dashboard dédié** ou une **carte Lovelace Quitoque**.

> [!IMPORTANT]
> Cette intégration est un projet communautaire non officiel. Elle n'est ni développée, ni maintenue, ni supportée par Quitoque.

<a name="toc-section-2"></a>

## ✨ Fonctionnalités

- Connexion au compte Quitoque directement depuis le **config flow** Home Assistant.
- Reconnexion automatique unique lorsque la session web Quitoque expire, avant de déclencher une réauthentification Home Assistant.
- Détection des **livraisons actives** et exclusion des semaines suspendues.
- Gestion des cinq échéances **S0 à S+4** : semaine en cours, semaine prochaine, puis les trois semaines suivantes.
- S0/S+1 proviennent des **box commandées** ; S+2/S+3/S+4 des prochaines box actives.
- Nombre de recettes prévu pour chacune des cinq semaines.
- Date et créneau horaire de livraison lorsqu'ils sont disponibles.
- Récupération des métadonnées des recettes et produits culinaires utilisés dans Home Assistant :
  - image de la recette ou du produit
  - temps en cuisine lorsqu'il est disponible
  - nombre de portions
- Prise en charge des **recettes classiques Quitoque**.
- Prise en charge des **kits culinaires du Marché Quitoque** lorsqu'ils disposent d'une fiche recette complète.
- Prise en charge des **plats cuisinés du Marché** lorsqu'un nombre de portions est indiqué sur leur fiche produit.
- Exclusion automatique des produits du Marché qui ne correspondent pas à un plat ou une recette exploitable, par exemple les produits d'épicerie, boulangerie ou autres articles sans indication de portions.
- Gestion des recettes en partenariat avec un chef sans créer de fausse recette à partir du sticker ou du visuel promotionnel associé.
- Sélection de l'image principale du plat ou de la recette en ignorant les logos et stickers promotionnels.
- Cache persistant des métadonnées afin d'éviter de recharger inutilement les mêmes informations après un redémarrage de Home Assistant.
- Ajout des recettes dans un calendrier Home Assistant ou un calendrier Google exposé à Home Assistant.
- Création d'un événement **journée entière** pour la livraison.
- Création d'événements recette d'une heure entre **08:00 et 11:00**.
- Titre des recettes sous la forme `PRÉFIXE Sn° - Nom de la recette` avec `Sn°` correspondant au numéro de la semaine.
- Préfixe d'événement personnalisable.
- Anti-doublon basé sur **l'année + le numéro de semaine**, même si les événements ont ensuite été déplacés dans le calendrier.
- Import de plusieurs semaines en une seule synchronisation.
- Actualisation manuelle sans recharger l'intégration.
- Notification Home Assistant optionnelle après une synchronisation du calendrier.
- Génération d'un **PDF par recette**, avec image, durée, portions et ingrédients/quantités lorsqu'ils sont fournis par Quitoque.
- Téléchargement individuel des PDF ou de l'ensemble dans une archive ZIP via des liens signés temporaires (30 minutes), sans exposition des fichiers dans `/config/www`.
- Suppression automatique des PDF après un délai configurable.
- Verrouillage temporaire des boutons pendant une actualisation, une synchronisation ou une génération PDF.
- Six entités de **diagnostic persistantes** mémorisent la dernière synchronisation du calendrier, la dernière génération des PDF, la dernière connexion réussie, la dernière reconnexion automatique, le résultat de la dernière action et la dernière erreur, y compris après un redémarrage de Home Assistant.
- **Dashboard Quitoque** permettant de consulter les prochaines livraisons et d'accéder rapidement aux principales actions.
- **Carte Lovelace Quitoque Card intégrée**, sans installation séparée, avec affichage des recettes, images, temps en cuisine, portions et plusieurs modes de présentation.
- Interface disponible en **français et anglais**.

<a name="toc-section-3"></a>

## 🛡️ Compatibilité

**Cette intégration dépend de l'interface web de Quitoque. Une modification du site peut donc nécessiter une mise à jour de l'intégration.**

Si une page ou une donnée n'est plus détectée, ouvrez une issue en fournissant les journaux **sans donnée d'authentification**.

<a name="toc-section-4"></a>

## 📦 Installation

### Option A — Marketplace (anciennement HACS ; Home Assistant >= 2026.11)

1. Ouvrez **Paramètres → Marketplace**.
2. Recherchez **Quitoque** dans le catalogue.
3. Ouvrez la fiche de l'intégration et choisissez **Installer**.
4. Suivez les indications affichées par Home Assistant. Redémarrez uniquement si cela vous est demandé.
5. Ajoutez ensuite l'intégration depuis **Paramètres → Appareils et services → Ajouter une intégration → Quitoque**.

### Option B — HACS classique

Sur Home Assistant 2026.10 et versions antérieures, retrouvez **Quitoque** directement dans le catalogue HACS, sans ajouter de dépôt personnalisé.

[![Ouvrir le dépôt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=quitoque&owner=AuroreVgn)

Ou depuis HACS :

1. Ouvrez **HACS → Intégrations**.
2. Recherchez **Quitoque**.
3. Sélectionnez l'intégration et choisissez **Télécharger**.
4. Redémarrez Home Assistant si nécessaire, puis ajoutez l'intégration depuis **Paramètres → Appareils et services**.

### Option C — Installation manuelle

1. Téléchargez l'archive de la [dernière release](https://github.com/AuroreVgn/quitoque/releases/latest).
2. Dans le répertoire contenant `configuration.yaml`, créez si nécessaire `custom_components`.
3. Placez le contenu du composant dans `/config/custom_components/quitoque`.
4. Redémarrez Home Assistant, puis ajoutez l'intégration depuis **Paramètres → Appareils et services**.

<a name="toc-section-5"></a>

## ⚙️ Configuration

Après l'installation :

**Paramètres → Appareils et services → Ajouter une intégration → Quitoque**

Renseigner :

| Paramètre | Description |
| --- | --- |
| Adresse e-mail / identifiant | Identifiant utilisé sur Quitoque |
| Mot de passe | Mot de passe Quitoque |
| URL de la page des recettes | Facultatif ; laisser vide pour la détection automatique |
| Préfixe personnalisé | Facultatif, par exemple `QT` |
| Conservation des PDF | Nombre de jours avant suppression ; `0` = ne jamais supprimer |
| Notification après synchronisation | Facultatif ; affiche une notification Home Assistant avec le nombre d’événements créés |
| Calendrier de destination | Calendrier Home Assistant dans lequel créer les événements |

### S0 et S+1 : box commandées

À partir de la version **1.2.0**, l’intégration complète les prochaines box avec les commandes de la **semaine en cours (S0)** et de la **semaine prochaine (S+1)** présentes dans « Mes box commandées ». L’identifiant Quitoque de la commande est conservé comme clé stable. Une commande peut donc passer de S+2 à S+1 puis S0 sans être recréée comme une nouvelle commande.

La déduplication du calendrier reste fondée sur l’**année ISO + le numéro de semaine**, ce qui évite également les collisions lors du passage S52/S53 → S01 d’une nouvelle année. Si Quitoque expose temporairement la même commande à la fois dans les prochaines box et les box commandées, elle est fusionnée par son identifiant de commande.

<a name="toc-section-6"></a>

## 📊 Entités créées

### Capteurs

| Entité | Description |
| --- | --- |
| Livraison cette semaine | Date de la livraison de S0, sinon `Non` |
| Livraison dans 1 semaine | Date de la livraison de S+1, sinon `Non` |
| Livraison dans 2 semaines | Date de la livraison active prévue dans deux semaines, sinon `Non` |
| Livraison dans 3 semaines | Date de la livraison active prévue dans trois semaines, sinon `Non` |
| Livraison dans 4 semaines | Date de la livraison active prévue dans quatre semaines, sinon `Non` |
| Nombre de recettes cette semaine | Nombre de recettes de S0, `0` si aucune box |
| Nombre de recettes dans 1 semaine | Nombre de recettes de S+1, `0` si aucune box |
| Nombre de recettes dans 2 semaines | Nombre de recettes de S+2, `0` si aucune box active |
| Nombre de recettes dans 3 semaines | Nombre de recettes de S+3, `0` si aucune box active |
| Nombre de recettes dans 4 semaines | Nombre de recettes de S+4, `0` si aucune box active |
| Dernière synchronisation du calendrier | Date et heure de la dernière synchronisation réussie ; valeur conservée après redémarrage |
| Dernière génération des PDF | Date et heure de la dernière génération PDF réussie ; valeur conservée après redémarrage |
| Dernière connexion réussie | Date et heure de la dernière authentification Quitoque réussie ; valeur conservée après redémarrage |
| Dernière reconnexion automatique | Date et heure de la dernière reconnexion automatique après expiration de session ; valeur conservée après redémarrage |
| Résultat de la dernière action Quitoque | Résultat de la dernière action Quitoque (`Succès`, `Erreur` ou `Aucune livraison`) ; valeur conservée après redémarrage |
| Dernière erreur | Dernier message d’erreur enregistré, ou `Aucune` ; valeur conservée après redémarrage |

Les six entités de suivi — dernière synchronisation, dernière génération PDF, dernière connexion réussie, dernière reconnexion automatique, résultat de la dernière action et dernière erreur — sont classées dans la catégorie **Diagnostic** de l’appareil.

Les capteurs de livraison exposent également des attributs utiles tels que le numéro de semaine, l'année, le début et la fin de semaine, le créneau de livraison et l'identifiant de commande lorsqu'ils sont disponibles.

### Métadonnées des recettes

Les capteurs **Nombre de recettes** exposent également les recettes de la semaine dans leurs attributs.

L'attribut `recipes` fournit une liste simple des noms de recettes et reste disponible pour assurer la compatibilité avec les dashboards et cartes existants.

L'attribut `recipe_details` fournit les informations enrichies utilisées notamment par la carte Lovelace.

Les éléments remontés peuvent provenir de plusieurs types de contenu Quitoque :

- recettes classiques ;
- kits culinaires proposés dans le Marché ;
- plats cuisinés du Marché lorsqu'ils disposent d'une indication de portions.

Les produits du Marché sans indication permettant de les identifier comme plat ou recette sont ignorés.

Exemple :

```yaml
recipes:
  - Bowl d'aubergine, ricotta fouettée à l'aneth
  - Soupe de butternut au parmesan et poitrine fumée croustillante
  - Lasagnes à la bolognaise (1kg)

recipe_details:
  - name: Bowl d'aubergine, ricotta fouettée à l'aneth
    kitchen_duration_minutes: 35
    duration_minutes: 35
    servings: 2 personnes
    image_url: https://...

  - name: Soupe de butternut au parmesan et poitrine fumée croustillante
    kitchen_duration_minutes: 35
    duration_minutes: 35
    servings: 2 personnes
    image_url: https://...

  - name: Lasagnes à la bolognaise (1kg)
    kitchen_duration_minutes:
    duration_minutes:
    servings: 3 personnes
    image_url: https://...
```

> [!NOTE]
> Le **temps total** de la recette n'est volontairement pas exposé dans ces métadonnées. Quitoque ne le fournit pas de manière suffisamment homogène selon les différentes pages. L'intégration conserve donc le **temps en cuisine**, qui est la donnée fiable.
> 
> Les métadonnées sont mises en cache de manière persistante par Home Assistant. Lors d'un redémarrage, les recettes déjà connues peuvent être restaurées sans refaire l'ensemble des requêtes réseau. Le cache est automatiquement nettoyé lorsque les commandes sortent de la plage S0 à S+4.
>
> Certaines fiches produit, notamment les plats cuisinés, ne fournissent pas de durée de préparation exploitable. Dans ce cas, l'intégration conserve les champs de durée vides mais continue de remonter les autres informations disponibles, notamment le nom, l'image et le nombre de portions.

### Boutons

| Bouton | Action |
| --- | --- |
| **Actualiser** | Interroge immédiatement Quitoque sans recharger l'intégration |
| **Ajouter les recettes au calendrier** | Ajoute les semaines actives absentes du calendrier |
| **Générer et télécharger les PDF** | Génère les fiches recettes et l'archive ZIP |

<a name="toc-section-7"></a>

## 📈 Dashboard Quitoque

Un **dashboard Quitoque** peut être utilisé pour regrouper dans une même vue les informations et commandes principales de l'intégration.

Il permet notamment d'afficher :

- les livraisons des semaines **S0 à S+4**
- la date de livraison
- le nombre de recettes de chaque semaine
- les recettes associées
- les principales informations remontées par l'intégration

Le dashboard permet également d'accéder rapidement aux actions :

- **Actualiser** les données Quitoque
- **Ajouter les recettes au calendrier**
- **Générer les PDF**
- **Ouvrir un calendrier** à partir d'une URL personnalisable.

L'affichage est conçu pour s'adapter à la largeur disponible afin de rester utilisable sur différentes tailles d'écran.

Il est disponible [ici](https://github.com/AuroreVgn/quitoque/tree/main/dashboard).

> [!NOTE]
> Le dashboard est un complément à l'intégration. Les entités Quitoque restent utilisables librement dans n'importe quel autre dashboard Home Assistant.

<a name="toc-section-8"></a>

## 🧩 Carte Lovelace — Quitoque Card

La carte Quitoque est **incluse dans l'intégration** : il n'est plus nécessaire d'installer séparément le dépôt `quitoque_card`.

Après installation et redémarrage de Home Assistant, la ressource **Module JavaScript** est enregistrée automatiquement :

```text
/quitoque/quitoque-card.js
```

Ajoutez une carte manuelle `type: custom:quitoque-card` ou utilisez son éditeur graphique.

> **Migration depuis l'ancienne carte HACS :** désinstallez l'ancienne carte séparée et supprimez uniquement son ancienne ressource JavaScript dans Paramètres → Tableaux de bord → Ressources, si elle existe. Conservez `/quitoque/quitoque-card.js`. Les configurations YAML `type: custom:quitoque-card` sont conservées.

Les captures d'écran historiques restent disponibles dans [le dépôt de la carte](https://github.com/AuroreVgn/quitoque_card/tree/main/assets).

### Configuration minimale

Une fois la ressource chargée, ajouter une carte manuelle :

```yaml
type: custom:quitoque-card
```

La carte utilise par défaut les noms d'entités classiques de l'intégration Quitoque.

Toutes les entités peuvent également être sélectionnées depuis l'éditeur graphique.



### Exemple de configuration complète

```yaml
type: custom:quitoque-card

title: Quitoque
display_mode: detailed
show_empty_weeks: true
show_actions: true
recipes_collapsed: false
show_recipe_images: true
image_size: medium

delivery_week_0: sensor.quitoque_livraison_cette_semaine
delivery_week_1: sensor.quitoque_livraison_dans_1_semaine
delivery_week_2: sensor.quitoque_livraison_dans_2_semaines
delivery_week_3: sensor.quitoque_livraison_dans_3_semaines
delivery_week_4: sensor.quitoque_livraison_dans_4_semaines

recipe_count_week_0: sensor.quitoque_nombre_de_recettes_cette_semaine
recipe_count_week_1: sensor.quitoque_nombre_de_recettes_dans_1_semaine
recipe_count_week_2: sensor.quitoque_nombre_de_recettes_dans_2_semaines
recipe_count_week_3: sensor.quitoque_nombre_de_recettes_dans_3_semaines
recipe_count_week_4: sensor.quitoque_nombre_de_recettes_dans_4_semaines

refresh_button: button.quitoque_actualiser
calendar_button: button.quitoque_ajouter_les_recettes_au_calendrier
pdf_button: button.quitoque_generer_et_telecharger_les_pdf

# Facultatif si plusieurs instances Quitoque sont configurées.
config_entry_id: ""

calendar_url: /calendar
calendar_url_name: Ouvrir calendrier
```

> [!NOTE]
> Dans l'éditeur graphique, `config_entry_id` n'est pas saisi manuellement : Home Assistant propose directement les instances Quitoque disponibles dans un menu déroulant.



#### 📊 Entités utilisées

#### Livraisons

Par défaut :

```yaml
delivery_week_0: sensor.quitoque_livraison_cette_semaine
delivery_week_1: sensor.quitoque_livraison_dans_1_semaine
delivery_week_2: sensor.quitoque_livraison_dans_2_semaines
delivery_week_3: sensor.quitoque_livraison_dans_3_semaines
delivery_week_4: sensor.quitoque_livraison_dans_4_semaines
```

#### Recettes

Par défaut :

```yaml
recipe_count_week_0: sensor.quitoque_nombre_de_recettes_cette_semaine
recipe_count_week_1: sensor.quitoque_nombre_de_recettes_dans_1_semaine
recipe_count_week_2: sensor.quitoque_nombre_de_recettes_dans_2_semaines
recipe_count_week_3: sensor.quitoque_nombre_de_recettes_dans_3_semaines
recipe_count_week_4: sensor.quitoque_nombre_de_recettes_dans_4_semaines
```

#### Boutons Quitoque

Par défaut :

```yaml
refresh_button: button.quitoque_actualiser
calendar_button: button.quitoque_ajouter_les_recettes_au_calendrier
pdf_button: button.quitoque_generer_et_telecharger_les_pdf
```

Le bouton **Supprimer** n'utilise pas une entité `button.*`. Il appelle directement le service :

```text
quitoque.cleanup_pdfs
```

Si plusieurs instances de l'intégration Quitoque sont configurées, l'instance concernée peut être choisie depuis l'éditeur graphique.



### Modes d'affichage

#### Détaillé

Le mode **Détaillé** affiche :

- la livraison sélectionnée ;
- sa date ;
- son créneau ;
- son statut ;
- le nombre de recettes ;
- les fiches de recettes avec image, durée en cuisine et portions.

Exemple :

```text
Quitoque

Actualiser | Calendrier | PDF | Supprimer

S0   S+1   S+2   S+3   S+4

Prochaine box
mercredi 26 août 2026
08h00 → 13h00
dans 4 jours
BOX ACTIVE

Recettes (4)

[IMAGE] Tarte de bricks aux nectarines...
        Cuisine 45 min
        2 personnes
```

#### Compact

Le mode **Compact** fournit une vue synthétique de S0 à S+4 avec le nombre de recettes de chaque semaine.

Il est adapté aux dashboards où l'espace disponible est limité.

#### Planning

Le mode **Planning** présente les semaines sous forme de liste :

```text
S0   mercredi 26 août   08h00 → 13h00   4 🍽️
S+1  mercredi 2 sept.   08h00 → 13h00   3 🍽️
S+2  Aucune livraison                    —
```



### Éditeur graphique

La carte fournit un éditeur Home Assistant permettant de configurer directement les options sans modifier le YAML.

#### Affichage

Les options disponibles comprennent notamment :

- **Titre**
- **Mode d'affichage**
  - Détaillé
  - Compact
  - Planning
- **Afficher aussi les semaines sans livraison**
- **Afficher les boutons d'action**
- **Replier les recettes par défaut**
- **Afficher les images des recettes**
- **Taille des images**
  - Petite
  - Moyenne
  - Grande

#### Sélection des entités et de l'instance Quitoque

L'éditeur permet de sélectionner :

- les 5 capteurs de livraison ;
- les 5 capteurs de recettes ;
- le bouton Actualiser ;
- le bouton Ajouter au calendrier ;
- le bouton PDF ;
- l'**instance Quitoque utilisée pour la suppression des PDF**.

Les champs utilisent les sélecteurs natifs Home Assistant.

Le choix de l'instance Quitoque est facultatif lorsqu'une seule instance de l'intégration est configurée.



### Boutons d'action

Les boutons Quitoque sont affichés directement sous le titre de la carte et au-dessus des semaines S0 à S+4.

Ils sont disposés sur une seule ligne :

```text
Actualiser | Calendrier | PDF | Supprimer
```

#### Actualiser

Appuie sur :

```text
button.quitoque_actualiser
```

et force une mise à jour immédiate des données Quitoque.

Pendant l'action, la carte affiche :

```text
Actualisation…
```

#### Calendrier

Appuie sur :

```text
button.quitoque_ajouter_les_recettes_au_calendrier
```

et lance la synchronisation avec le calendrier configuré dans l'intégration.

Pendant l'action :

```text
Synchronisation…
```

#### PDF

Appuie sur :

```text
button.quitoque_generer_et_telecharger_les_pdf
```

et lance la génération des fiches PDF.

Pendant l'action :

```text
Génération PDF…
```

#### Supprimer

Appelle directement le service :

```text
quitoque.cleanup_pdfs
```

et supprime les PDF et archives générés par l'intégration Quitoque.

Pendant l'action :

```text
Suppression…
```

Si plusieurs instances Quitoque sont configurées, l'instance cible peut être choisie dans l'éditeur graphique grâce au sélecteur natif Home Assistant.

Les autres boutons sont temporairement désactivés pendant l'exécution d'une action.



### Calendrier personnalisé

La carte peut également afficher un bouton indépendant permettant d'ouvrir un calendrier ou n'importe quelle URL.

Ce bouton apparaît dans l'en-tête de la carte, à droite du résumé du nombre de box et de recettes.

Deux champs sont disponibles dans l'éditeur :

```text
URL du calendrier externe
Nom du bouton calendrier
```

#### Exemples d'URL

Calendrier Home Assistant :

```text
/calendar
```

ou simplement :

```text
calendar
```

Une route Home Assistant personnalisée :

```text
/lovelace/calendrier
```

Un calendrier externe :

```text
https://calendar.google.com/
```

Une URL saisie sans protocole telle que :

```text
calendar.google.com
```

est automatiquement interprétée comme :

```text
https://calendar.google.com
```

Sur mobile, le bouton calendrier externe peut être réduit à son icône afin de conserver un en-tête compact.



### Images des recettes

La carte utilise :

```yaml
image_url
```

dans l'attribut `recipe_details`.

Si aucune image n'est disponible, une icône :

```text
mdi:chef-hat
```

est affichée à la place.

Les images utilisent le chargement différé (`loading="lazy"`).

Les images déjà chargées sont réutilisées lors des mises à jour, afin de limiter le clignotement sur Safari iOS. Les changements d’état sans rapport avec Quitoque ne reconstruisent plus la carte.



### Recettes repliables

En mode détaillé, la liste des recettes peut être ouverte ou fermée.

L'option :

```text
Replier les recettes par défaut
```

permet de choisir son état initial.



### Semaines sans livraison

La carte distingue plusieurs états :

- livraison active
- aucune box
- entité indisponible
- entité absente

Si l'option :

```text
Afficher aussi les semaines sans livraison
```

est désactivée, seules les semaines disposant d'une box sont conservées dans la navigation, lorsqu'il existe au moins une livraison active.



### Responsive / mobile

La carte adapte automatiquement sa présentation à la largeur disponible.

Sur petit écran :

- S0 à S+4 deviennent horizontalement défilables ;
- les 4 actions restent disposées sur une seule ligne ;
- le résumé de l'en-tête est simplifié ;
- le bouton calendrier externe utilise principalement son icône ;
- les images de grande taille sont réduites.





<a name="toc-section-9"></a>

## 📅 Calendrier

Le bouton **Ajouter les recettes au calendrier** traite les box des semaines **S0 à S+4**.

Les commandes de S0 et S+1 sont lues dans les box commandées ; S+2 à S+4 restent issues des prochaines box actives.

Les éléments pouvant être ajoutés au calendrier comprennent :

- les recettes classiques ;
- les kits culinaires du Marché ;
- les plats cuisinés du Marché identifiés comme tels par leur fiche produit.

Les produits du Marché qui ne correspondent pas à une recette ou à un plat sont automatiquement exclus.

Pour chaque livraison :

- un événement **journée entière** est créé le jour de la livraison ;
- les recettes sont ajoutées sous forme d'événements d'une heure à partir de **08:00** ;
- le créneau de livraison est ajouté au texte de l'événement lorsqu'il est disponible ;
- le numéro de semaine est conservé dans le titre ;
- le préfixe configuré est ajouté avant le numéro de semaine.

Exemple avec le préfixe `QT` :

```text
QT S36 - Bowl d'aubergine, ricotta fouettée à l'aneth
```

Le titre de l’événement de journée entière inclut le créneau récupéré chez Quitoque, par exemple `QT S36 - Livraison Quitoque - 08h00 - 13h00`.

### Protection contre les doublons

Chaque semaine importée reçoit un marqueur interne basé sur **l'année et le numéro de semaine**.

Ainsi :

```text
2026 / S36
```

et :

```text
2027 / S36
```

sont considérées comme deux livraisons différentes.

Le contrôle ne repose pas uniquement sur la date actuelle de l'événement : une recette déplacée manuellement dans le calendrier reste reconnue comme appartenant à sa semaine Quitoque d'origine.

<a name="toc-section-10"></a>

## 📅 Utilisation avec Google Calendar

Quitoque peut ajouter les livraisons et les recettes à un calendrier Google **via Home Assistant**. Il n'est pas nécessaire de connecter Quitoque directement à Google : le calendrier doit simplement être accessible dans Home Assistant et autoriser la création d'événements.

### Configuration pas à pas

1. Dans Home Assistant, installer et configurer l'intégration **[Google Calendar](https://www.home-assistant.io/integrations/google/)** en suivant sa documentation officielle.
2. Vérifier que le calendrier Google souhaité apparaît dans Home Assistant sous la forme d'une entité `calendar` et que la création d'événements est autorisée.
3. Ouvrir **Paramètres → Appareils et services → Quitoque → Configurer**.
4. Dans **Calendrier de destination**, sélectionner l'entité du calendrier Google.
5. Utiliser le bouton **Ajouter les recettes au calendrier** de l'intégration Quitoque (ou l'action `quitoque.sync_calendar`).
6. Ouvrir **[Google Calendar](https://calendar.google.com/)** et vérifier les événements créés : la livraison sur la journée entière et les recettes sous forme d'événements d'une heure.

> [!NOTE]
> - La synchronisation vers Google Calendar passe par Home Assistant et est déclenchée par le bouton ou l'action Quitoque : **elle n'est pas continue par défaut**. Pour la lancer automatiquement, il est possible de créer une automatisation Home Assistant appelant `quitoque.sync_calendar`.
> - La protection anti-doublon de Quitoque empêche de réimporter une semaine déjà enregistrée, même si ses événements ont été déplacés manuellement dans le calendrier.
> - Si le calendrier n'apparaît pas dans la liste, vérifier qu'il est bien exposé par l'intégration Google Calendar et qu'il prend en charge la création d'événements.

**Liens utiles :** [Documentation Google Calendar pour Home Assistant](https://www.home-assistant.io/integrations/google/) · [Ouvrir Google Calendar](https://calendar.google.com/)

<a name="toc-section-11"></a>

## 📄 PDF des recettes

Le bouton **Générer et télécharger les PDF** récupère le détail des recettes et kits disposant d'une fiche recette exploitable et crée :

- un PDF par recette ou kit ;
- l'image principale de la recette lorsqu'elle est disponible ;
- une mise en page imprimable de la fiche ;
- la durée lorsqu'elle est fournie par Quitoque ;
- le nombre de portions lorsqu'il est disponible ;
- les ingrédients fournis **dans votre box** et leurs quantités ;
- les éléments **dans votre cuisine** dans une section distincte ;
- le **matériel** dans une troisième section distincte ;
- le déroulé de la recette étape par étape ;
- une archive ZIP regroupant les PDF générés.

Les plats cuisinés qui ne disposent pas d'un véritable déroulé de recette restent disponibles dans Home Assistant et dans le calendrier, mais ne sont pas traités comme une fiche recette complète pour la génération PDF.

Le délai de conservation est configurable dans les options de l'intégration. Une valeur de `0` désactive la suppression automatique.

<a name="toc-section-12"></a>

## 🥕 Recettes et produits du Marché

Quitoque utilise plusieurs catégories de produits dans une même commande.

L'intégration distingue désormais :

| Type | Pris en charge | Image | Portions | Étapes / PDF |
| --- | --- | --- | --- | --- |
| Recette classique | ✅ | ✅ | ✅ | ✅ |
| Kit culinaire du Marché | ✅ | ✅ | ✅ | ✅ |
| Plat cuisiné du Marché | ✅ | ✅ | ✅ si disponible | Selon la fiche |
| Produit classique du Marché | ❌ | — | — | — |

Un produit du Marché n'est donc pas automatiquement considéré comme une recette.

Pour les plats cuisinés, l'intégration utilise notamment l'indication de portions présente sur la fiche produit afin de distinguer un véritable plat des autres articles du Marché.

<a name="toc-section-13"></a>

## 🎛️ Options

Les options peuvent être modifiées depuis :

**Paramètres → Appareils et services → Quitoque → Configurer**

Il est possible de modifier :

- l'URL de la page des recettes
- le calendrier de destination
- le préfixe des événements
- le délai de conservation des PDF
- l’activation de la notification après synchronisation

<a name="toc-section-14"></a>

## 🔧 Services Home Assistant

En plus des boutons de l'appareil, l'intégration expose des services utilisables dans les scripts et automatisations :

```yaml
action: quitoque.refresh
```

```yaml
action: quitoque.sync_calendar
```

```yaml
action: quitoque.generate_pdfs
```

Pour supprimer immédiatement les PDF et le ZIP générés :

```yaml
action: quitoque.cleanup_pdfs
```

Pour supprimer immédiatement le ZIP généré :

```yaml
action: quitoque.delete_archive
```

Avec un seul compte Quitoque, aucun paramètre n'est nécessaire. Si plusieurs comptes sont configurés, renseignez `config_entry_id`.

Les services utilisent exactement les mêmes mécanismes que les boutons : verrouillage pendant l'exécution, gestion de S0 à S+4, anti-doublon calendrier et mise à jour des capteurs de diagnostic.

<a name="toc-section-15"></a>

## 🛠️ Dépannage

### Reconnexion automatique

Quitoque utilise une session web qui peut expirer après plusieurs heures. À partir de la version **1.1.0**, une expiration normale de session ne déclenche plus immédiatement une demande de réauthentification Home Assistant.

L’intégration tente automatiquement **une seule reconnexion** avec les identifiants déjà enregistrés, récupère un nouveau jeton CSRF puis rejoue la requête interrompue.

- si la reconnexion réussit, l’intégration continue sans intervention ;
- si la reconnexion échoue (mot de passe modifié, compte refusé ou mécanisme de connexion Quitoque modifié), le flux standard de **réauthentification Home Assistant** est conservé ;
- aucune boucle de connexion n’est effectuée : une seule tentative automatique est autorisée par requête.

Les diagnostics **Dernière connexion réussie** et **Dernière reconnexion automatique** permettent de vérifier le fonctionnement de ce mécanisme.

Pour activer les journaux détaillés :

```yaml
logger:
  default: info
  logs:
    custom_components.quitoque: debug
```

Après redémarrage, les messages sont disponibles dans **Paramètres → Système → Journaux**.

> [!WARNING]
> Ne publiez jamais vos cookies de session, votre mot de passe ou un jeton CSRF dans une issue GitHub.

<a name="toc-section-16"></a>

## 🤝 Contributions et problèmes

Les retours, corrections et propositions d'amélioration sont les bienvenus via les [issues GitHub](https://github.com/AuroreVgn/quitoque/issues).

Lors d'un signalement, pensez à indiquer :

- la version de Home Assistant ;
- la version de l'intégration Quitoque ;
- le comportement attendu ;
- les logs pertinents anonymisés.

<a name="toc-section-17"></a>

## 📄 Licence

Projet distribué sous licence [MIT](LICENSE).

[releases-shield]: https://img.shields.io/github/v/release/AuroreVgn/quitoque?style=flat-square
[releases]: https://github.com/AuroreVgn/quitoque/releases
[license-shield]: https://img.shields.io/github/license/AuroreVgn/quitoque?style=flat-square

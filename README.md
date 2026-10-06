# 🥕 Quitoque

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5.svg?style=flat-square&logo=homeassistant)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz/)
[![Maintainer](https://img.shields.io/badge/Maintainer-AuroreVgn-blue.svg?style=flat-square)](https://github.com/AuroreVgn)

## ☕️ Soutenir le projet

Si cette intégration vous est utile et que vous souhaitez soutenir son développement et sa maintenance :

<p>
  <a href="https://ko-fi.com/aurorevgn">
    <img src="https://storage.ko-fi.com/cdn/kofi4.png?v=3"
         alt="Support me on Ko-fi"
         height="45">
  </a>
</p>

## 🏠 Mes projets Home Assistant

Retrouvez l'ensemble de mes intégrations et projets Home Assistant sur ma page dédiée : [**🏠 Découvrir mes projets Home Assistant**](https://gentle-suggestion-7c3.notion.site/Mes-projets-Home-Assistant-3eda02eefa8f81a48621c3caeef7fa8e)

## ⚠️ Important
Intégration personnalisée **Home Assistant** permettant de récupérer les prochaines recettes d'un compte **Quitoque**, de suivre les livraisons de **S0 à S+4**, de les ajouter à un calendrier Home Assistant (ou Google), de générer les fiches recettes en PDF et d'afficher les informations dans un **dashboard dédié** ou une **carte Lovelace Quitoque**.

> [!IMPORTANT]
> Cette intégration est un projet communautaire non officiel. Elle n'est ni développée, ni maintenue, ni supportée par Quitoque.

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
- Téléchargement individuel des PDF ou de l'ensemble dans une archive ZIP.
- Suppression automatique des PDF après un délai configurable.
- Verrouillage temporaire des boutons pendant une actualisation, une synchronisation ou une génération PDF.
- Six entités de **diagnostic persistantes** mémorisent la dernière synchronisation du calendrier, la dernière génération des PDF, la dernière connexion réussie, la dernière reconnexion automatique, le résultat de la dernière action et la dernière erreur, y compris après un redémarrage de Home Assistant.
- **Dashboard Quitoque** permettant de consulter les prochaines livraisons et d'accéder rapidement aux principales actions.
- **Carte Lovelace Quitoque Card** avec affichage des recettes, images, temps en cuisine, portions et plusieurs modes de présentation.
- Interface disponible en **français et anglais**.

## Entités créées

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

## Installation

### Option A — HACS (recommandé)

#### Automatiquement

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AuroreVgn&repository=quitoque&category=integration)

#### Manuellement

Cette intégration étant un dépôt personnalisé, il faut l'ajouter une première fois dans HACS :

1. Ouvrir **HACS** → **Intégrations**.
2. Ouvrir le menu **⋮** → **Dépôts personnalisés**.
3. Ajouter :

   ```text
   https://github.com/AuroreVgn/quitoque
   ```

4. Choisir la catégorie **Intégration**.
5. Rechercher **Quitoque** dans HACS puis installer l'intégration.
6. Redémarrer Home Assistant.

### Option B — Installation manuelle

1. Télécharger la dernière version du dépôt.
2. Copier le dossier :

   ```text
   custom_components/quitoque
   ```

   dans :

   ```text
   /config/custom_components/quitoque
   ```

3. Redémarrer Home Assistant.

## Configuration

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

## Dashboard Quitoque

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

## Carte Lovelace — Quitoque Card

Une carte Lovelace dédiée, **Quitoque Card**, est également disponible pour afficher les informations Quitoque directement dans un tableau de bord Home Assistant.

Elle est disponible [ici](https://github.com/AuroreVgn/quitoque_card).

## Calendrier

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

## Utilisation avec Google Calendar

L'intégration écrit dans une entité `calendar` Home Assistant. Elle peut donc utiliser un calendrier Google dès lors que celui-ci est exposé dans Home Assistant par l'intégration Google Calendar et qu'il accepte la création d'événements.

Il suffit de sélectionner ce calendrier dans le champ **Calendrier de destination** lors de la configuration de Quitoque.

## PDF des recettes

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

## Recettes et produits du Marché

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

## Options

Les options peuvent être modifiées depuis :

**Paramètres → Appareils et services → Quitoque → Configurer**

Il est possible de modifier :

- l'URL de la page des recettes
- le calendrier de destination
- le préfixe des événements
- le délai de conservation des PDF
- l’activation de la notification après synchronisation

## Services Home Assistant

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

## Dépannage

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

## Compatibilité

**Cette intégration dépend de l'interface web de Quitoque. Une modification du site peut donc nécessiter une mise à jour de l'intégration.**

Si une page ou une donnée n'est plus détectée, ouvrez une issue en fournissant les journaux **sans donnée d'authentification**.

## Contributions et problèmes

Les retours, corrections et propositions d'amélioration sont les bienvenus via les [issues GitHub](https://github.com/AuroreVgn/quitoque/issues).

Lors d'un signalement, pensez à indiquer :

- la version de Home Assistant ;
- la version de l'intégration Quitoque ;
- le comportement attendu ;
- les logs pertinents anonymisés.

## Licence

Projet distribué sous licence [MIT](LICENSE).

[releases-shield]: https://img.shields.io/github/v/release/AuroreVgn/quitoque?style=flat-square
[releases]: https://github.com/AuroreVgn/quitoque/releases
[license-shield]: https://img.shields.io/github/license/AuroreVgn/quitoque?style=flat-square

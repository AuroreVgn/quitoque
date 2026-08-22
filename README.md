# Quitoque

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5.svg?style=flat-square&logo=homeassistant)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz/)
[![Maintainer](https://img.shields.io/badge/Maintainer-AuroreVgn-blue.svg?style=flat-square)](https://github.com/AuroreVgn)


Intégration personnalisée **Home Assistant** permettant de récupérer les prochaines recettes d'un compte **Quitoque**, de les ajouter à un calendrier Home Assistant (ou Google) et de générer les fiches recettes en PDF.

> [!IMPORTANT]
> Cette intégration est un projet communautaire non officiel. Elle n'est ni développée, ni maintenue, ni supportée par Quitoque.

## ✨ Fonctionnalités

- Connexion au compte Quitoque directement depuis le **config flow** Home Assistant.
- Reconnexion automatique unique lorsque la session web Quitoque expire, avant de déclencher une réauthentification Home Assistant.
- Détection des **livraisons actives** et exclusion des semaines suspendues.
- Gestion volontairement limitée aux trois échéances **S+2, S+3 et S+4** : livraisons et recettes dans 2, 3 et 4 semaines.
- Nombre de recettes prévu pour chacune de ces trois semaines.
- Date et créneau horaire de livraison lorsqu'ils sont disponibles.
- Ajout des recettes dans un calendrier Home Assistant ou un calendrier Google exposé à Home Assistant.
- Création d'un événement **journée entière** pour la livraison.
- Création d'événements recette d'une heure entre **08:00 et 11:00**.
- Titre des recettes sous la forme `PRÉFIXE Sn° - Nom de la recette` avec `Sn°` correspond au numéro de la semaine.
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
- Interface disponible en **français et anglais**.

## Entités créées

### Capteurs

| Entité | Description |
| --- | --- |
| Livraison dans 2 semaines | Date de la livraison active prévue dans deux semaines, sinon `Non` |
| Livraison dans 3 semaines | Date de la livraison active prévue dans trois semaines, sinon `Non` |
| Livraison dans 4 semaines | Date de la livraison active prévue dans quatre semaines, sinon `Non` |
| Nombre de recettes dans 2 semaines | Nombre de recettes de la box correspondante, `0` si aucune box active |
| Nombre de recettes dans 3 semaines | Nombre de recettes de la box correspondante, `0` si aucune box active |
| Nombre de recettes dans 4 semaines | Nombre de recettes de la box correspondante, `0` si aucune box active |
| Dernière synchronisation du calendrier | Date et heure de la dernière synchronisation réussie ; valeur conservée après redémarrage |
| Dernière génération des PDF | Date et heure de la dernière génération PDF réussie ; valeur conservée après redémarrage |
| Dernière connexion réussie | Date et heure de la dernière authentification Quitoque réussie ; valeur conservée après redémarrage |
| Dernière reconnexion automatique | Date et heure de la dernière reconnexion automatique après expiration de session ; valeur conservée après redémarrage |
| Résultat de la dernière action Quitoque | Résultat de la dernière action Quitoque (`Succès`, `Erreur` ou `Aucune livraison`) ; valeur conservée après redémarrage |
| Dernière erreur | Dernier message d’erreur enregistré, ou `Aucune` ; valeur conservée après redémarrage |

Les six entités de suivi — dernière synchronisation, dernière génération PDF, dernière connexion réussie, dernière reconnexion automatique, résultat de la dernière action et dernière erreur — sont classées dans la catégorie **Diagnostic** de l’appareil.

Les capteurs de livraison exposent également des attributs utiles tels que le numéro de semaine ISO, l'année ISO, le début et la fin de semaine, le créneau de livraison et l'identifiant de commande lorsqu'ils sont disponibles.

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


## Calendrier

Le bouton **Ajouter les recettes au calendrier** traite uniquement les box actives des semaines **S+2, S+3 et S+4**. Les autres semaines ne sont volontairement pas gérées.

Pour chaque livraison :

- un événement **journée entière** est créé le jour de la livraison
- les recettes sont ajoutées sous forme d'événements d'une heure à partir de **08:00**
- le créneau de livraison est ajouté au texte de l'événement lorsqu'il est disponible
- le numéro de semaine est conservé dans le titre
- le préfixe configuré est ajouté avant le numéro de semaine

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

Le bouton **Générer et télécharger les PDF** récupère le détail des recettes des prochaines box actives et crée :

- un PDF par recette
- l'image de la recette lorsqu'elle est disponible
- une mise en page imprimable de la fiche
- la durée et le nombre de portions lorsqu'ils sont disponibles
- les ingrédients fournis **dans votre box** et leurs quantités
- les éléments **dans votre cuisine** dans une section distincte
- le **matériel** dans une troisième section distincte
- le déroulé de la recette étape par étape
- une archive ZIP regroupant les PDF générés

Lors d'une nouvelle génération, l'archive ZIP précédente est remplacée.

Le délai de conservation est configurable dans les options de l'intégration. Une valeur de `0` désactive la suppression automatique.

## Options

Les options peuvent être modifiées depuis :

**Paramètres → Appareils et services → Quitoque → Configurer**

Il est possible de modifier :

- l'URL de la page des recettes ;
- le calendrier de destination ;
- le préfixe des événements ;
- le délai de conservation des PDF ;
- l’activation de la notification après synchronisation.

## Services Home Assistant

En plus des boutons de l'appareil, l'intégration expose quatre services utilisables dans les scripts et automatisations :

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

Pour supprimer immédiatement  le ZIP générés :
```yaml
action: quitoque.delete_archive
```


Avec un seul compte Quitoque, aucun paramètre n'est nécessaire. Si plusieurs comptes sont configurés, renseignez `config_entry_id`.

Les services utilisent exactement les mêmes mécanismes que les boutons : verrouillage pendant l'exécution, gestion de S+2/S+3/S+4, anti-doublon calendrier et mise à jour des capteurs de diagnostic.



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

- la version de Home Assistant
- la version de l'intégration Quitoque
- le comportement attendu
- les logs pertinents anonymisés

## Licence

Projet distribué sous licence [MIT](LICENSE).


[releases-shield]: https://img.shields.io/github/v/release/AuroreVgn/quitoque?style=flat-square
[releases]: https://github.com/AuroreVgn/quitoque/releases
[license-shield]: https://img.shields.io/github/license/AuroreVgn/quitoque?style=flat-square

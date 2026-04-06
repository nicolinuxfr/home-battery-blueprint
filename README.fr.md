# solar-battery-blueprint

Projet de blueprint Home Assistant multilingue pour piloter jusqu'à quatre batteries à partir d'un seul capteur de puissance maison. Le blueprint se concentre sur la décharge, peut absorber un export réel via une charge opportuniste, et combine entités `number` directes et actions personnalisées par batterie.

Ce blueprint est volontairement générique. Il n'essaie pas d'unifier les APIs propres à chaque marque. À la place, chaque slot batterie peut être piloté par :

- des entités `number` modifiables pour la décharge et/ou la charge
- des actions personnalisées pour la décharge et/ou la charge
- les deux à la fois si une batterie a besoin d'une consigne directe plus d'étapes propres à son intégration

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fsolar-battery-blueprint%2Fgh-pages%2Ffr%2Funiversal_home_battery_power_manager.yaml)

URL brute d'import :

`https://raw.githubusercontent.com/nicolinuxfr/solar-battery-blueprint/gh-pages/fr/universal_home_battery_power_manager.yaml`

## Configuration

- `Capteur de puissance maison` : capteur principal utilisé par l'algorithme. Il doit suivre la convention `import > 0` et `export < 0`.
- `Marge de décharge` : watts soustraits à la demande maison avant de démarrer la décharge.
- `Entité de blocage global` : quand cette entité est à `off`, toutes les batteries gérées reviennent à neutre et toutes les actions d'arrêt sont exécutées.
- `Delta minimal de commande` : ignore les petits changements de cible.

Pour chaque slot batterie :

- `Capteur d'état de charge` : laisser vide désactive le slot.
- `Capteur de puissance réelle` : capteur signé optionnel utilisé comme indice de sécurité.
- `Puissance maximale de décharge` et `Puissance maximale de charge` : limites manuelles utilisées par l'algorithme.
- `Prioritaire en décharge` : les batteries prioritaires se vident d'abord ; la charge opportuniste préfère d'abord les batteries non prioritaires.
- `Cooldown de commande` : délai anti-spam par batterie.
- `Entité number de décharge directe` et `Entité number de charge directe` : entités de pilotage direct optionnelles.
- `Actions de mise/arrêt de décharge` et `Actions de mise/arrêt de charge` : actions personnalisées optionnelles, avec des variables d'exécution comme `battery_slot`, `battery_soc`, `target_discharge_w`, `target_charge_w`, `house_power_w` et `export_surplus_w`.

## Fonctionnement

- À chaque run, le blueprint choisit un seul mode exclusif : `discharge`, `charge` ou `neutral`.
- En décharge, il répartit `max(house_power - margin, 0)` entre les batteries, en privilégiant d'abord les batteries marquées prioritaires puis en triant par pourcentage de charge décroissant.
- En charge opportuniste, il détecte un export réel, exige qu'au moins une batterie soit à `99 %` ou plus, puis remplit les batteries chargeables du SOC le plus bas vers le plus haut, en évitant autant que possible les batteries prioritaires en décharge.
- La sécurité passe avant tout : passer en charge coupe d'abord tous les chemins de décharge gérés, et passer en décharge coupe d'abord tous les chemins de charge gérés. Le blueprint ne cherche jamais à faire charger et décharger en même temps des batteries qu'il pilote lui-même.

## Limites connues

- Le blueprint ne crée pas lui-même de capteur de moyenne glissante. Si tu veux un signal lissé, fournis en entrée un capteur déjà filtré.
- Une seule entité directe bidirectionnelle n'est pas supportée en couple charge/décharge. Utilise des actions personnalisées dans ce cas.
- Pour les batteries pilotées uniquement par actions, les actions d'arrêt devraient être idempotentes, car le blueprint peut devoir les rejouer pour la sécurité.
- Le capteur de puissance réelle optionnel fonctionne au mieux lorsqu'il est signé : positif en décharge, négatif en charge.
- Le metadata du blueprint et la documentation pointent vers `nicolinuxfr/solar-battery-blueprint`.

# home-battery-blueprint

Projet de blueprint Home Assistant multilingue pour piloter jusqu'à quatre batteries à partir d'un seul capteur de puissance maison. Le blueprint répartit la décharge, peut absorber un export réel via une charge opportuniste, peut charger pendant les heures creuses selon une cible calculée depuis la prévision solaire du lendemain, et écrit pour chaque batterie une consigne de puissance signée dans une entité numérique. Des actions optionnelles restent disponibles pour les intégrations qui ont besoin d'un mode ou d'un service séparé. Chaque batterie est rangée dans sa propre section repliée par défaut pour garder un formulaire compact.

Ce blueprint est volontairement générique. Il n'essaie pas d'unifier les APIs propres à chaque marque. À la place, chaque slot batterie activé est piloté par :

- une entité numérique de consigne signée, mise à jour par le blueprint
- des actions personnalisées optionnelles pour la charge et/ou la décharge quand une intégration a besoin d'un mode séparé
- un helper signé ou une entité de device directe, selon ce que l'intégration accepte réellement

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fhome-battery-blueprint%2Fgh-pages%2Ffr%2Fhome_battery_manager.yaml)

URL brute d'import :

`https://raw.githubusercontent.com/nicolinuxfr/home-battery-blueprint/gh-pages/fr/home_battery_manager.yaml`

## Configuration

- `Capteur de puissance maison` : capteur principal utilisé par l'algorithme. Le sélecteur n'affiche que les capteurs de puissance, mais Home Assistant ne permet pas de filtrer l'unité ici, donc il faut toujours choisir un capteur signé en `W` avec `import > 0` et `export < 0`.
- `Entités heures creuses actives` : liste optionnelle d'entités `binary_sensor`, `input_boolean` ou `schedule`. Si au moins une entité vaut `on`, le blueprint ne commande plus de décharge et peut charger les slots autorisés pour les heures creuses. Ce champ remplace l'ancien champ `Entités de blocage` et casse volontairement son ancienne sémantique.
- `Import maison maximal pendant la charge heures creuses` : plafond global en watts. Le blueprint estime l'import maison hors charge des batteries gérées et n'alloue que la puissance restante. Mets `0 W` pour désactiver la charge heures creuses.
- `Capteur de prévision solaire demain` : capteur d'énergie en `kWh`. Une valeur valide à `0 kWh` fait viser `100 %`. Un capteur vide, indisponible ou non numérique empêche la charge heures creuses prédictive de démarrer.
- `Part de prévision solaire à réserver` : pourcentage de la production prévue à garder libre dans les batteries. Avec `10 kWh` de capacité utile et `50 %`, une prévision de `8 kWh` réserve `4 kWh` et vise environ `60 %`.

Pour chaque slot batterie :

- `Capteur d'état de charge` : laisser vide désactive le slot. Le sélecteur n'affiche que les capteurs de batterie qui remontent un pourcentage. Si tu le renseignes, le slot doit aussi exposer une entité numérique de consigne et au moins une puissance max non nulle.
- `Puissance maximale de décharge` et `Puissance maximale de charge` : limites manuelles utilisées par l'algorithme. La limite de charge sert à la fois pour la charge opportuniste et la charge heures creuses.
- `Capacité utile` : capacité en `kWh` utilisée pour calculer la cible SoC de charge heures creuses.
- `Charger pendant les heures creuses` : autorise ce slot à participer à la charge heures creuses. Le slot doit aussi avoir une capacité utile, une puissance maximale de charge et une entité de consigne.
- `Entité de consigne de puissance` : entité `number` ou `input_number` écrite par le blueprint. La consigne est signée : positive en décharge, négative en charge, `0` à l'arrêt. Si tu actives la charge, l'entité choisie doit accepter les valeurs négatives.
- `Capteur de puissance réelle` : capteur optionnel qui remonte la puissance réellement fournie par la batterie. Le blueprint continue d'utiliser l'entité de consigne et le compteur maison comme boucle principale. Après le délai de réponse, une mesure valide non périmée sert seulement de garde-fou pour éviter de compter une batterie comme apport réel quand elle ne délivre plus. Une mesure périmée n'empêche pas une batterie au repos de démarrer. Si la télémétrie reste périmée après qu'une consigne active a eu le temps de produire un effet, cette batterie est exclue des allocations de décharge additionnelles tandis que sa consigne déjà active peut rester en place sauf arrêt, changement de signe ou export réel imposant une correction.
- `Cooldown de commande` : délai par batterie entre deux mises à jour actives de consigne, et signal principal utilisé pour déterminer la réactivité d'une batterie. Plus il est court, plus la batterie traite en premier les variations résiduelles. Plus il est long, plus elle garde une consigne active stable pendant que les batteries plus rapides absorbent les changements de demande. Mets `0` pour supprimer complètement ce délai. Les passages à `0`, les inversions de signe et les redémarrages depuis `0` quand le compteur maison brut confirme un import ou export correspondant restent immédiats pour ne pas retarder un arrêt, un changement de sens ou la reprise d'une batterie utile. Un export brut peut aussi réduire une consigne de décharge active avant la fin du cooldown.
- `Actions de décharge` et `Actions de charge` : hooks optionnels exécutés à chaque mise à jour active dans le sens correspondant, puis à nouveau quand le blueprint doit arrêter une batterie qui débite ou charge encore physiquement. Ils reçoivent des variables d'exécution comme `battery_slot`, `battery_soc`, `target_power_w`, `target_discharge_w`, `target_charge_w`, `house_power_w` et `export_surplus_w`.

Exemple Zendure :

- crée un helper signé tel que `input_number.zendure_virtual_p1`
- configure l'option `p1meter` de l'intégration Zendure sur ce helper
- renseigne ce helper dans `Entité de consigne de puissance`
- laisse les actions de charge et de décharge vides si l'intégration Zendure consomme déjà ce helper directement

## Fonctionnement

- À chaque run, le blueprint choisit un seul mode exclusif : `discharge`, `charge`, `off_peak_charge`, `off_peak_idle` ou `neutral`.
- Pendant les heures creuses actives, le blueprint ne commande aucune décharge. Si la prévision solaire, la capacité utile ou le plafond d'import ne permettent pas de charger, il passe en `off_peak_idle` et remet les batteries gérées à neutre.
- La cible de charge heures creuses est calculée ainsi : `marge_kwh = min(prévision_kwh * part_réservée / 100, capacité_totale)`, puis `cible_soc = 100 - marge_kwh / capacité_totale * 100`.
- La charge heures creuses démarre de manière échelonnée après activation : première batterie éligible à `+15 min`, deuxième à `+30 min`, troisième à `+45 min`, quatrième à `+60 min`. L'ordre privilégie le SoC le plus bas, puis le cooldown le plus court.
- Le plafond d'import maison est appliqué sur l'import estimé hors charge des batteries déjà gérées. Si la maison consomme déjà presque tout le plafond, la charge est réduite ou arrêtée.
- Il émet aussi désormais un événement structuré `home_battery_blueprint_run` à chaque exécution autorisée, avant tout arrêt anticipé ou écriture par slot. Cet événement contient la source du déclenchement, la raison de décision, le mode retenu, les puissances maison, les consignes calculées, l'état des cooldowns, les erreurs de validation et un snapshot JSON de chaque slot batterie avec consigne courante, consigne signée désirée, puissance réelle, âge de la puissance réelle, état périmé de cette puissance réelle, état de redémarrage depuis zéro confirmé et écritures/actions prévues.
- Les valeurs du capteur maison ne sont acceptées que si Home Assistant les considère comme des nombres finis valides. Les états non numériques, dont `unknown`, `unavailable`, `NaN` et l'infini, sont traités comme un capteur invalide au lieu d'être silencieusement convertis en `0 W`.
- Les runs déclenchés par le capteur de puissance maison ignorent maintenant les mises à jour qui ne changent que les attributs, et ils s'arrêtent aussi très tôt si la variation numérique reste sous un seuil interne de `10 W` uniquement quand le run serait réellement sans effet. Si une petite variation implique malgré tout une écriture de consigne ou une action personnalisée active, le blueprint continue au lieu d'ignorer ce run. Les entités heures creuses déclenchent immédiatement sans passer par ce seuil.
- En décharge, les consignes déjà actives forment d'abord la base stable. Le résiduel est ensuite donné aux batteries disponibles triées par cooldown le plus court, ce qui laisse les batteries réactives suivre les variations sans déplacer les batteries à long cooldown à chaque petit changement.
- Les batteries à `90 %` de charge ou plus sont promues avant l'ordre résiduel normal en décharge afin de recréer une marge avant la pleine charge. Ces mêmes batteries à SoC élevé sont relâchées plus tard lors des réductions de décharge et remplies plus tard en charge opportuniste.
- Quand deux batteries ont le même cooldown, celle avec le SoC le plus élevé peut reprendre la main sur une batterie active au SoC plus bas au lieu d'attendre derrière sa consigne existante.
- Quand la demande baisse, la décharge est réduite dans l'ordre inverse : les batteries au cooldown le plus court sont relâchées d'abord. Si un export réel reste présent, les batteries capables de charger et au cooldown court peuvent absorber temporairement cet excès au lieu d'attendre que les intégrations lentes acceptent leur prochaine consigne.
- L'allocateur reconstruit la demande maison sous-jacente à partir du capteur maison net en réajoutant la contribution effective de chaque batterie gérée : la consigne active quand aucun capteur de puissance réelle n'est configuré ou pendant la fenêtre de réponse, puis la dernière puissance mesurée valide tant qu'elle n'est pas périmée. Une batterie qui continue à débiter ou charger physiquement après une consigne revenue à `0` est aussi comptée et réservée dans l'allocation suivante, pour éviter que le blueprint ajoute la même puissance sur une autre batterie. Une télémétrie configurée mais non numérique ou très périmée contribue `0` jusqu'à ce que la batterie soit relancée ou remonte à nouveau une mesure valide.
- Quand un capteur optionnel de puissance réelle est configuré, le blueprint l'utilise après le délai de réponse pour détecter qu'une batterie délivre durablement nettement moins que sa consigne active. Cette correction ne remplace jamais la boucle principale basée sur la consigne et le compteur maison.
- Si une batterie garde une consigne de décharge active mais que sa télémétrie valide non périmée montre qu'elle ne délivre pratiquement plus rien après le délai de réponse, ou que son capteur de puissance réelle configuré reste périmé après la fenêtre de réponse, elle est temporairement exclue des allocations de décharge additionnelles. Sa consigne active peut rester maintenue pour la stabilité, mais sa contribution mesurée n'est pas comptée, ce qui laisse les batteries plus rapides couvrir le résiduel. Une batterie au repos avec télémétrie périmée peut encore démarrer ; le garde-fou s'applique seulement après que la consigne a eu le temps de produire un effet. L'événement de run expose cet état avec `actual_power_usable`, `actual_power_stale`, `discharge_delivery_stalled` et `discharge_available`.
- Pendant un cooldown ou une phase de latence, le blueprint continue de raisonner à partir de la consigne déjà active et de l'effet observé sur la consommation nette de la maison, sans dépendre d'une télémétrie batterie lente ou irrégulière.
- Chaque run capture un seul timestamp et le réutilise pour les âges de consigne, les âges de puissance réelle et les vérifications de cooldown par slot. Les garde-fous de cooldown en charge et en décharge partagent le même calcul de temps écoulé avant d'appliquer leurs checks de capacité propres à chaque sens.
- Lorsqu'une batterie vient de recevoir une nouvelle consigne, le blueprint réserve cette puissance demandée pendant son délai de réponse, pendant que les batteries plus rapides ne prennent que le résiduel restant.
- Si le compteur maison brut montre déjà un export pendant la décharge, le blueprint réduit les consignes de décharge même pendant le cooldown, en relâchant d'abord les batteries au cooldown le plus court et en ne conservant qu'une réserve de décharge encore compatible avec le compteur brut. Cela évite qu'une réserve devenue trop optimiste maintienne un gros export pendant tout le cooldown.
- Quand une mesure de puissance réelle fraîche montre qu'une batterie débite encore au-dessus d'une nouvelle allocation de décharge plus basse pendant sa fenêtre de réponse, la réduction anti-export crédite d'abord cette baisse déjà en cours avant de couper davantage la consigne. Cela évite de trop réduire une batterie réactive et de provoquer un rebond en import réseau, sans dépendre d'une deuxième écriture avant cooldown qu'une intégration cloud pourrait refuser.
- Si une réallocation demande d'augmenter une batterie alors qu'une autre batterie doit encore baisser mais reste verrouillée par son cooldown, l'augmentation n'est bloquée que pour la part qui dépasse l'import réel mesuré. Le blueprint préfère alors un court import réseau à un pic d'export causé par deux consignes temporairement incompatibles, sans empêcher une batterie disponible de répondre à une vraie demande maison.
- Cette réduction sur export brut s'applique aussi quand une consigne de décharge est maintenue dans la zone morte neutre. Si toutes les consignes de décharge ont été réduites et qu'il reste encore au moins le seuil de relâchement de `10 W` d'export brut, le blueprint peut utiliser temporairement les batteries capables de charger qui n'ont plus de consigne de décharge dans ce run pour absorber le pic résiduel, en privilégiant le cooldown de commande le plus court.
- Si de l'export brut reste présent après les réductions de décharge réellement applicables dans le run courant, les batteries capables de charger peuvent absorber temporairement cet export brut restant. Une batterie capable de charger qui débite encore physiquement pendant un export brut ne compte plus sa baisse de décharge demandée comme déjà absorbée, ce qui permet au chemin de charge opportuniste de l'inverser vers la charge au lieu d'attendre d'abord que la décharge se stabilise. Avec la bande morte de commande maintenant à `10 W`, les batteries réactives capables de charger peuvent absorber directement un petit export.
- Le calcul de charge lit maintenant directement le plan de décharge calculé, sans dépendre des variables helper de consigne de décharge par slot qui sont définies plus tard dans le même run.
- En charge opportuniste, il réagit à tout export réel qui reste après avoir retiré la contribution de décharge déjà pilotée par les batteries gérées, puis remplit les batteries capables de charger en privilégiant le cooldown le plus court et le SOC le plus bas. Cela laisse les batteries réactives absorber l'export au lieu de l'envoyer au réseau.
- La bande morte de commande et le seuil de relâchement internes valent tous les deux `10 W`, ce qui permet aux batteries réactives de corriger les petites variations d'import/export au lieu de laisser un résiduel volontaire plus large. La batterie au cooldown le plus court reste prioritaire pour ces corrections, afin de garder les batteries plus lentes plus stables quand une batterie rapide peut absorber la variation.
- Quand un export brut fort continue alors qu'une batterie réactive capable de charger débite encore physiquement, le blueprint applique un frein de latence temporaire et peut abaisser la consigne de décharge de cette batterie sous l'allocation stable, jusqu'à `0 W`. Cela accepte un possible court rebond en import pour réduire l'export pendant que les intégrations lentes appliquent la commande, puis laisse le chemin de charge opportuniste prendre le relais si cette même batterie peut absorber l'export.
- Une deuxième bande morte interne de `10 W` sur la consigne saute maintenant les corrections dans le même sens en dessous de ce seuil. Cela supprime les micro-ajustements bruyants et les relances inutiles d'actions personnalisées quand la puissance demandée ne bouge que de quelques watts, tout en laissant passer immédiatement les arrêts forcés, les inversions de signe et les réductions de décharge imposées par la protection contre l'export.
- En zone morte `neutral`, le blueprint conserve maintenant la contribution déjà en cours des batteries gérées au lieu de retomber immédiatement à `0`. Cela évite les cycles marche/arrêt quand une batterie vient juste de compenser presque toute la demande maison.
- Quand la consigne signée calculée s'arrondit à la même valeur que celle déjà présente sur l'entité de consigne, le blueprint saute désormais cette écriture redondante et ne relance pas non plus les actions personnalisées dans le même sens. Cela réduit les appels de service sans effet et les effets de bord dupliqués côté intégrations, tout en conservant les vrais changements de consigne, les inversions de signe et les arrêts forcés.
- La consigne écrite par le blueprint est signée : positive en décharge, négative en charge, `0` en neutre. Un passage à `0`, un capteur invalide, une entrée en heures creuses, une inversion de signe ou un démarrage depuis `0` pendant que le compteur maison brut confirme le flux réseau correspondant provoquent une écriture immédiate sans attendre le cooldown. Pendant un cooldown actif, le blueprint réserve toujours par défaut la puissance déjà commandée sur cette batterie, mais un export brut autorise une baisse de consigne de décharge avant la fin du cooldown.
- Les corrections dans le même sens sur une batterie déjà active respectent toujours le cooldown, sauf arrêt forcé, changement de signe ou réduction de décharge imposée par la protection contre l'export. Cela évite les consignes bruyantes tout en permettant à une batterie au repos de reprendre quand la maison importe réellement depuis le réseau.
- Si une entité de consigne refuse une mise à jour, par exemple parce que l'intégration impose son propre délai minimal entre deux changements, l'automatisation continue maintenant et met quand même à jour les autres slots batterie.
- La validation s'exécute maintenant avant toute écriture par batterie ou action personnalisée. Chaque commande non nulle est revérifiée contre l'état courant du capteur maison juste avant l'exécution, et les heures creuses actives forcent le mode `off_peak_charge` ou `off_peak_idle` avant toute logique de décharge.
- Les actions optionnelles de charge et de décharge tournent uniquement quand la batterie est active dans le sens correspondant. Elles sont utiles pour les intégrations qui ont besoin d'un `select`, d'un service additionnel, ou d'une traduction helper -> API vendor.
- Les étapes internes de l'automatisation portent maintenant des noms explicites pour que les traces Home Assistant affichent plus clairement, pendant le debug, les écritures de consigne par batterie, les hooks de charge/décharge et les arrêts de validation.
- Si un slot activé est incomplet, l'automatisation s'arrête avec un message de validation explicite indiquant s'il manque l'entité de consigne ou si les deux puissances sont à `0 W`.

## Limites connues

- Le blueprint ne crée pas lui-même de capteur de moyenne glissante. Si tu veux un signal lissé, fournis en entrée un capteur déjà filtré.
- Si une batterie doit charger, l'entité de consigne choisie doit accepter les valeurs négatives. Sinon, utilise un helper signé intermédiaire.
- La batterie réactive disponible au cooldown le plus court peut recevoir de petites consignes non nulles jusqu'à la bande interne de `10 W` afin d'effacer le résiduel restant. Cela s'applique aux consignes de décharge et de charge disponibles, même quand la batterie est actuellement au repos. Si l'entité de consigne expose un minimum positif supérieur à cette petite consigne de décharge, le blueprint borne normalement la valeur écrite à ce minimum, mais écrit plutôt `0` quand le compteur maison brut exporte déjà.
- Les actions optionnelles ne tournent pas en neutre. Si ton intégration a besoin d'une traduction explicite du `0`, passe par un helper signé que l'intégration ou une autre automatisation consomme.
- Les métadonnées du blueprint et la documentation pointent vers `nicolinuxfr/home-battery-blueprint`.

## Capture de logs 24 h

Le moyen le plus simple pour me renvoyer un historique exploitable est de capturer les événements `home_battery_blueprint_run` dans un fichier JSONL.

Un package Home Assistant prêt à copier est fourni dans [examples/home_battery_blueprint_diagnostics_package.yaml](/Users/nicolas/Developer/domotique/home-battery-blueprint/examples/home_battery_blueprint_diagnostics_package.yaml).

Étapes :

1. Active les `packages` Home Assistant si ce n'est pas déjà fait :

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. Copie [examples/home_battery_blueprint_diagnostics_package.yaml](/Users/nicolas/Developer/domotique/home-battery-blueprint/examples/home_battery_blueprint_diagnostics_package.yaml) vers `/config/packages/home_battery_blueprint_diagnostics.yaml`.
3. Redémarre Home Assistant.
4. Laisse tourner 24 h.
5. Récupère `/config/home_battery_blueprint_runs.jsonl` et renvoie-le-moi.

Conseils :

- Supprime le fichier `/config/home_battery_blueprint_runs.jsonl` avant une nouvelle capture pour repartir proprement.
- Le fichier contient une ligne JSON par run du blueprint, ce qui est facile à filtrer ou compresser avant envoi.

# Livraison politique / approbation / résultat — 2026-11-07

Branch `audit/native-security-acceptance-20261107`, base a8fef1f préservée. Tout ajout est dans cette worktree ; aucun fichier de la worktree Backend ni de native-installers n'a été édité.

## Interface à intégrer avec Backend Data

`delivery.action_review.ActionReview(controls, resolver)` est un hook interne, sans route web. Le resolver doit lire sur `tx.conn` un bundle canonique persisté, son contexte exact, son origine immuable et la révision **courante** de l'incident, sous le verrou existant 72611027. Signature : `resolver(tx, decision_id) -> (bundle, context, origin, current_incident_revision)`. Ce hook ne doit jamais recevoir un contexte ou un statut d'executor attesté par un formulaire/LLM. Le Backend reste propriétaire du resolver, des évaluations et du dossier ; aucune implémentation de ces éléments n'a été dupliquée.

`approve(decision_id, expected_action, expected_revision, actor, now)` revalide les gates existants, crée un nouveau snapshot autorisé avec `supersedes_decision_id` et conserve le pending original. M1 ne change pas ; l'approbation ne lance aucune simulation. Elle est spécifique au fingerprint, à la décision, à sa politique, à l'incident/révision et à sa validité. L'acteur doit venir d'une session authentifiée, pas du JSON du navigateur.

`simulate(decision_id, expected_revision, actor, now)` exige SIMULATION et une décision autorisée par politique ou approbation spécifique, revalide contexte/gates/profil/révision, puis écrit une seule fois résultat SIMULATED et vérification NOT_PERFORMED. L'origine n'est jamais modifiée, notamment après approbation admin. Aucun adaptateur REAL n'existe ; aucune réussite de défense ni mitigation confirmée n'est inventée. Le code ne prétend pas lever un executor_ready absent : ce gate doit provenir du registre d'executor de simulation authentifié. Origine inconnue => refus explicite.

Le contrat canonique reste inchangé, y compris `execution_requested=false`. L'évaluation existante du Backend reste indépendante : elle n'appelle pas ActionReview. Il reste à valider ensemble ses transactions PostgreSQL et le parcours M1 complet. Les événements d'évaluation n'ont pas été simulés artificiellement dans le test de persistance des approbations.

## PostgreSQL et paquet nativo

Migration additive `backend/delivery/006_action_review.sql`, table `hs_action_review`, clés `(kind,decision_id)` ; enregistrements approval/result/verification distincts. Chaque écriture journalise ACTION_APPROVAL/ACTION_RESULT/ACTION_VERIFICATION dans `hs_control_audit`, avec mode historique et origine. Aucune mise à jour d'un résultat existant. Le store utilise la même connexion/verrou que les contrôles.

La migration est reliée à `packaging/native/provision.py` et le module au gate `runtime_check.py`. Le build Windows collecte déjà le paquet delivery et tous ses SQL ; Ubuntu copie delivery et ses SQL. Aucune dépendance Python/driver/service supplémentaire ; utilise psycopg/jsonschema déjà déclarés. Aucun build d'installeur n'a été lancé et aucun payload final installé n'a été homologué. Un nouveau service ne sera nécessaire que si le Backend choisit un worker ; il devra alors être déclaré dans WinSW/systemd avec readiness et récupération.

## Résultats exécutés

- `security-fixture-result.json` : 22 tests réussis, dont 8 nouveaux sur approbation M1 sans changement/dispatch, refus sans approbation, reprise idempotente, origine, gates, urgence et matrice M1/M2/M3. Les tests interceptent Popen/os.system pour refuser les appels OS dans la simulation. Cela prouve l'absence d'appel de ces voies dans le hook testé, pas une mesure de firewall installé.
- `security-postgres-result.json` : 8 vérifications réussies dans un cluster natif PostgreSQL 18.4 neuf, exclusif au laboratoire de cette worktree, port 25439. Nouvelle connexion, mêmes résultats sans doublon, audits séparés, M1 historique conservé et migration rejouable sans perte. Cluster arrêté après l'essai ; aucun service système enregistré.
- Premier essai PostgreSQL interrompu après blocage du pipe hérité de pg_ctl, avant création des tables. Le cluster concerné a été arrêté explicitement ; le runner utilise maintenant DEVNULL. Le résultat publié correspond au nouvel essai achevé.

## Lacunes et runtimes

Prévia 5174 : non modifiée, nouveau hook non branché à son HTTP. Ubuntu installé et Windows installé : pas d'acceptation exécutée de cette livraison, pas de reboot/VM propre, pas de login/panneau/services automatiques attestés. Les machines restent identifiées par leurs VMX mais disponibilité actuelle non confirmée.

Pas de défense réelle Windows/Ubuntu : driver de capture éventuel, permissions Linux, adaptateurs de containment, contrôle de cible et vérification effective restent non livrés. Réponse de statut existante `containment=not_available`/executor non configuré doit rester affichée. L'absence de résultat lié doit rester absence explicite.

Restent avant activation : resolver persistant exact et authentifié ; projections liées de décision approuvée/approval/execution/verification vers le dossier (la table interne n'est pas un substitut transparent aux projections P11) ; enregistrement des producteurs dans l'autorité opérationnelle ; refus d'application de profil pendant activités/état inconnu ; session/anti-CSRF et audit des refus à l'interface HTTP ; test évaluation M1 + approbation + résultat en bout en bout. Aucun de ces points n'est déclaré homologué.

BitNet n'est pas importé/appelé. XAI ne fait pas partie de ce patch ; SHAP Tree/Permutation, sorties exactes RF/IF/Risk Engine et absence d'explication restent sous responsabilité Backend, à valider par runtime séparé.

# Liste des tâches de développement TrackImmo

## Phase 1: Fondations ✅

### Configuration du projet ✅

- [x] Initialiser le repository Git
- [x] Installer les dépendances de base (requirements.txt)
- [x] Configurer l'environnement de développement
- [x] Créer la structure de fichiers initiale

### Modèles de données ✅

- [x] Créer les modèles Pydantic partagés entre modules (ScrapedProperty, ProcessedProperty)
- [x] Créer les modèles SQLAlchemy mappés sur la structure SQL existante
- [x] Mettre en place les validateurs

### API minimale ✅

- [x] Configurer FastAPI avec la documentation OpenAPI
- [x] Créer les endpoints de base (sans implémentation)
- [x] Mettre en place l'authentification simple
- [x] Développer un endpoint de healthcheck

## Phase 2: Module Scraper

### Génération d'URLs

- [x] Implémenter le générateur d'URLs par ville/code postal
- [ ] Créer la logique de découpage géographique des zones
- [x] Développer le système de paramètres de recherche (dates, types de biens)
- [ ] Tester la génération d'URLs

### Configuration Playwright ✅

- [x] Mettre en place le browser manager avec Playwright
- [x] Configurer les options du navigateur headless
- [x] Implémenter la gestion des erreurs et retries
- [ ] Tester la connexion aux pages ImmoData

### Extraction des propriétés

- [x] Développer le parser HTML selon les sélecteurs (voir [SCRAPING.md](SCRAPING.md))
- [x] Implémenter l'extraction des détails de propriétés
- [x] Créer le système d'export CSV intermédiaire
- [ ] Tester l'extraction sur différents types de propriétés

## Phase 3: Module Processor ✅

### Parsing des données ✅

- [x] Développer le parser de CSV brut
- [x] Valider et nettoyer les données
- [x] Normaliser les formats d'adresses et de dates
- [x] Gérer les valeurs manquantes

### Service de géocodage

- [x] Implémenter l'interface avec l'API de géocodage (voir [GEOCODING_API.md](GEOCODING_API.md))
- [x] Développer le traitement par lots des adresses
- [x] Créer la logique de validation des résultats
- [ ] Tester le géocodage avec différents formats d'adresses

### Service DPE

- [x] Implémenter l'interface avec l'API DPE (voir [DPE_API.md](DPE_API.md))
- [x] Créer la logique de récupération et parsing des données énergétiques
- [x] Développer le système de matching des DPEs aux adresses
- [ ] Tester la récupération des DPEs

### Estimation des prix ✅

- [x] Implémenter l'algorithme d'estimation (voir [PRICE_ESTIMATION.md](PRICE_ESTIMATION.md))
- [x] Développer le calcul des scores de confiance
- [x] Créer la logique d'évolution temporelle des prix
- [ ] Tester l'estimation sur différents cas de figure

## Phase 4: Module DB Manager

### Interface SQLAlchemy ✅

- [x] Configurer la connexion à PostgreSQL
- [x] Créer les repositories pour chaque entité (City, Address, Client, etc.)
- [x] Implémenter les transactions simples
- [ ] Tester la connexion et les requêtes de base

### Import des données

- [ ] Développer l'import des villes et codes postaux
- [ ] Créer la logique d'import/mise à jour des adresses
- [ ] Gérer les conflits et duplications
- [ ] Tester l'import de différents jeux de données

### Matching client-propriété ✅

- [x] Implémenter l'algorithme de matching selon les règles métier
- [x] Développer la gestion des statuts de suivi
- [x] Créer les requêtes de récupération ciblées
- [ ] Tester le matching sur différents profils clients

## Phase 5: API et intégration ✅

### Implémentation des routes ✅

- [x] Développer les endpoints complets (voir [API_DOCS.md](API_DOCS.md))
- [x] Implémenter la gestion d'erreurs API
- [x] Créer les services d'orchestration entre modules
- [ ] Tester les endpoints individuellement

### Documentation OpenAPI ✅

- [x] Rédiger la documentation complète des endpoints
- [x] Ajouter les exemples de requêtes/réponses
- [x] Documenter les schémas de données
- [ ] Tester la documentation via Swagger UI

### Authentification simple ✅

- [x] Finaliser le système d'authentification par token
- [x] Implémenter les permissions selon les rôles
- [x] Créer les endpoints de gestion des utilisateurs
- [ ] Tester les différents scénarios d'authentification

## Phase 6: Tests et optimisations

### Tests unitaires ✅

- [x] Créer les tests pour les fonctions critiques de chaque module
- [x] Tester les cas nominaux uniquement
- [x] Mettre en place un système simple de rapports de tests
- [ ] Vérifier la stabilité des tests

### Optimisations ponctuelles

- [ ] Optimiser les requêtes SQL fréquentes
- [ ] Améliorer les performances du scraping si nécessaire
- [ ] Régler les problèmes de mémoire potentiels
- [ ] Tester les améliorations

### Robustesse et logging ✅

- [x] Améliorer le système de logging
- [x] Ajouter des métriques simples
- [x] Développer les retry patterns pour les services externes
- [ ] Tester la robustesse face aux erreurs externes

### Documentation ✅

- [x] Finaliser la documentation technique
- [x] Créer un guide de déploiement simple
- [x] Documenter les procédures de maintenance
- [ ] Préparer le handover

## Résumé de l'état d'avancement

- **Phase 1**: ✅ 100% Terminée
- **Phase 2**: ⏳ 70% Terminée (Manque tests et découpage géographique)
- **Phase 3**: ⏳ 85% Terminée (Manque tests)
- **Phase 4**: ⏳ 50% Terminée (Manque import de données et tests)
- **Phase 5**: ⏳ 85% Terminée (Manque tests)
- **Phase 6**: ⏳ 60% Terminée (Manque optimisations et robustesse)

### Prochaines tâches prioritaires

1. Tester l'extraction sur différents types de propriétés
2. Tester le géocodage avec différents formats d'adresses
3. Développer l'import des villes et codes postaux
4. Tester la connexion aux pages ImmoData
5. Tester les endpoints individuellement

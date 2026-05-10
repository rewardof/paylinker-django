# Changelog

All notable changes to **paylinker-django** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-05-11

### Changed
- Removed the `django<6.0` upper bound from install requirements.
  The package now declares `django>=4.2` so installations on projects
  pinning Django 6.x are no longer blocked by a dependency conflict.

## [0.1.0] - 2026-05-08

### Added
- Initial release.
- Reusable Django app (`paylinker_django`) integrating the
  [`paylinker`](https://pypi.org/project/paylinker/) core SDK.
- `ProviderTransaction` model + initial migration tracking Payme/Click
  transaction lifecycle, decoupled from any project's Order model.
- `DjangoPaymeTransactionHandler` — implements paylinker's full
  `TransactionHandler` protocol with idempotent state transitions.
- `DjangoClickOrderValidator` — implements paylinker's `OrderValidator`
  protocol with `select_for_update` locking on prepare/complete/cancel.
- Webhook views (`payme_webhook`, `click_webhook`) plus URL include
  (`paylinker_django.urls`).
- Single-dict `PAYLINKER` settings API with helper accessors
  (`get_payme_config`, `get_click_config`, `get_handler_class`).
- Django admin registration for `ProviderTransaction`.
- PEP 561 typing (`py.typed`).

[Unreleased]: https://github.com/tohirbek/paylinker-django/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/tohirbek/paylinker-django/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/tohirbek/paylinker-django/releases/tag/v0.1.0
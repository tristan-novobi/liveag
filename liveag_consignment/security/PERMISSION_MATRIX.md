# API v3 Permission Matrix (fill out)

Use this to define desired access per role. Then implement via `ir.model.access` (+ record rules where needed).

**Last Updated:** 2026-02-10
**Last Reviewed:** 2026-02-10

**Legend**

- **R** = Read
- **W** = Write
- **C** = Create
- **D** = Delete (unlink)
- **—** = No access
- **?** = To be decided / fill in

**Roles**

- **Manager** = `group_consignment_manager` (Commercial Cattle/Administrator)
- **Rep** = `group_consignment_rep`
- **Seller** = `group_consignment_seller`
- **Buyer** = `group_consignment_buyer`

---

## 1. Model access (ir.model.access)

Which CRUD should each role have on each model? Record rules (in `consignment_contract_security.xml`) then limit *which rows* they see.

**This table is aligned to every model in `ir.model.access.csv`** (same module). Base models (e.g. `res.partner`) are noted; access for them may come from base or this module.


| Model (technical name)                               | Manager | Rep     | Seller | Buyer | Notes                                                                  |
| ---------------------------------------------------- | ------- | ------- | ------ | ----- | ---------------------------------------------------------------------- |
| **Core (contracts, contacts, rep)**                  |         |         |        |       |                                                                        |
| consignment.contract                                 | R W C D | R W C   | R      | R     | Core contracts; rep rule exists.                                       |
| res.partner                                          | (base)  | R W C   | —      | —     | Access from base; this module only adds record rules. Rules exist.     |
| res.contact.type                                     | R W C D | R       | R      | R     | Partner roles (Seller, Buyer, Rep, etc.). Rep/Seller/Buyer: read-only. |
| res.rep                                              | R W C D | R W C D | —      | —     | Rep assignments.                                                       |
| sale.auction                                         | R W C D | R       | R      | R     | Auctions list/create.                                                  |
| **Contract-related**                                 |         |         |        |       |                                                                        |
| contract.activity.log                                | R W C D | —       | —      | —     | Activity log.                                                          |
| contract.addendum                                    | R W C D | R W C D | R      | R     | Used by consignment.contract.                                          |
| contract.deduction                                   | R W C D | —       | —      | —     | On consignment.contract model, but legacy and not shown in UI.         |
| catalog.change                                       | R W C D | R W C   | R      | R     | Catalog changes. Rules exist.                                          |
| **Metadata / list models (contract form dropdowns)** |         |         |        |       |                                                                        |
| sale.type                                            | R W C D | R       | R      | R     | base.group_user has R.                                                 |
| kind.list                                            | R W C D | R       | R      | R     | Metadata.                                                              |
| contract.type                                        | R W C D | R       | R      | R     | Metadata.                                                              |
| origin.list                                          | R W C D | R       | R      | R     | Metadata.                                                              |
| frame.size                                           | R W C D | R       | R      | R     | Metadata.                                                              |
| flesh.type                                           | R W C D | R       | R      | R     | Metadata.                                                              |
| weight.variance                                      | R W C D | R       | R      | R     | Metadata.                                                              |
| horns.list                                           | R W C D | R       | R      | R     | Metadata.                                                              |
| implanted.list                                       | R W C D | R       | R      | R     | Metadata.                                                              |
| castration.list                                      | R W C D | R       | R      | R     | Metadata.                                                              |
| bangs.vaccinated                                     | R W C D | R       | R      | R     | Metadata.                                                              |
| special.section                                      | R W C D | R       | R      | R     | Metadata.                                                              |
| genetic.merit                                        | R W C D | R       | R      | R     | Metadata.                                                              |
| premium.genetics.program                             | R W C D | R       | R      | R     | Metadata.                                                              |
| van.program                                          | R W C D | R       | R      | R     | Metadata.                                                              |
| third.party.age                                      | R W C D | R       | R      | R     | Metadata.                                                              |
| vac.program                                          | R W C D | R       | R      | R     | Metadata.                                                              |
| gap.program                                          | R W C D | R       | R      | R     | Metadata.                                                              |
| slide.type                                           | R W C D | R       | R      | R     | Metadata.                                                              |
| weight.stop                                          | R W C D | R       | R      | R     | Metadata.                                                              |
| whose.option                                         | R W C D | R       | R      | R     | Metadata.                                                              |
| location.type                                        | R W C D | R       | R      | R     | Metadata.                                                              |
| **Other reference / config**                         |         |         |        |       |                                                                        |
| res.region                                           | R W C D | R       | R      | R     | Region list.                                                           |
| res.partner.email                                    | R W C D | R       | R      | R     | Partner email records.                                                 |
| buyer.number                                         | R W C D | R       | R      | R     | Buyer numbers.                                                         |
| program.icon                                         | R W C D | R       | R      | R     | Icons for programs.                                                    |
| draft                                                | R W C D | R       | R      | R     | Draft contracts. (Covered under consignment.contract model)            |
| beef.checkoff                                        | R W C D | R       | R      | R     | Beef checkoff.                                                         |
| **Delivery**                                         |         |         |        |       |                                                                        |
| consignment.delivery                                 | R W C D | R W C D | R      | R     | Future release.                                                        |
| consignment.delivery.line                            | R W C D | —       | —      | —     | Delivery lines. Future release.                                        |
| consignment.delivery.check                           | R W C D | —       | —      | —     | Delivery checks. Future release.                                       |
| consignment.delivery.adjustment                      | R W C D | —       | —      | —     | Delivery adjustments. Future release.                                  |
| delivery.weight.mixin                                | R W C D | —       | —      | —     | Mixin (no UI). Future release.                                         |
| delivery.slide.mixin                                 | R W C D | —       | —      | —     | Mixin (no UI). Future release.                                         |
| delivery.financial.mixin                             | R W C D | —       | —      | —     | Mixin (no UI). Future release.                                         |
| delivery.monetary.mixin                              | R W C D | —       | —      | —     | Mixin (no UI). Future release.                                         |
| **Wizards (UI only; typically Manager)**             |         |         |        |       |                                                                        |
| split.contract.wizard                                | R W C D | —       | —      | —     | UI wizard.                                                             |
| buyer.report.wizard                                  | R W C D | —       | —      | —     | UI wizard.                                                             |
| seller.report.wizard                                 | R W C D | —       | —      | —     | UI wizard.                                                             |
| rep.report.wizard                                    | R W C D | —       | —      | —     | UI wizard.                                                             |
| buyer.email.send.wizard                              | R W C D | —       | —      | —     | UI wizard.                                                             |
| seller.email.send.wizard                             | R W C D | —       | —      | —     | UI wizard.                                                             |
| rep.email.send.wizard                                | R W C D | —       | —      | —     | UI wizard.                                                             |
| buyer.invoice.wizard                                 | R W C D | —       | —      | —     | UI wizard.                                                             |
| buyer.invoice.wizard.contract.line                   | R W C D | —       | —      | —     | UI wizard line.                                                        |
| delivery.sheet.wizard                                | R W C D | —       | —      | —     | UI wizard.                                                             |
| delivery.sheet.wizard.contract.line                  | R W C D | —       | —      | —     | UI wizard line.                                                        |
| merge.option.contracts.wizard                        | R W C D | —       | —      | —     | UI wizard.                                                             |
| merge.deliveries.wizard                              | R W C D | —       | —      | —     | UI wizard.                                                             |
| **Other**                                            |         |         |        |       |                                                                        |
| auction.report.email                                 | R W C D | —       | —      | —     | base.group_user has R.                                                 |
| res.users                                            | R W C D | —       | —      | —     | Custom extension (this module).                                        |


**Cross-check:** All 58 models in `ir.model.access.csv` (this module) are listed above. `res.partner` is from base; its row-level rules are in `consignment_contract_security.xml`. CSV model IDs use the pattern `model_<name>` (e.g. `model_consignment_contract` → `consignment.contract`).

---

## 2. API endpoints – who can call what?

Token-authenticated API v3 routes only; auth (e.g. request-access) and webhook routes use different auth and are not listed.

Put **Yes** if the role is allowed to call that endpoint (API will enforce via token user + Odoo ACL/record rules). Put **No** or **—** if not.


| Endpoint                                            | Method | Manager | Rep | Seller | Buyer | Notes                                      |
| --------------------------------------------------- | ------ | ------- | --- | ------ | ----- | ------------------------------------------ |
| /api/v3/me                                          | GET    | Yes     | Yes | Yes    | Yes   | Token user info.                           |
| /api/v3/contracts                                   | GET    | Yes     | Yes | Yes    | Yes   | List contracts (record rules filter rows). |
| /api/v3/contracts                                   | POST   | Yes     | Yes | No     | No    | Create contract.                           |
| /api/v3/contracts                                   | PUT    | Yes     | Yes | No     | No    | Update contract.                           |
| /api/v3/contracts/metadata/status                   | GET    | Yes     | Yes | Yes    | Yes   | Contract status list.                      |
| /api/v3/contracts/metadata/sale_type                | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/kind                     | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/contract_type            | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/origin                   | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/frame_size               | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/flesh_type               | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/weight_variance          | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/horns                    | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/implanted_type           | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/castration               | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/bangs_vaccinated         | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/special_section          | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/genetic_merit            | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/premium_genetics_program | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/van_program              | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/source_age_program       | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contracts/metadata/vac_program              | GET    | Yes     | Yes | Yes    | Yes   |                                            |
| /api/v3/contacts                                    | GET    | Yes     | Yes | No     | No    | List contacts (record rules filter).       |
| /api/v3/contacts                                    | POST   | Yes     | No  | No     | No    | Create contact.                            |
| /api/v3/contacts/sellers                            | GET    | Yes     | Yes | No     | No    | List sellers (rep’s assigned).             |
| /api/v3/auctions                                    | GET    | Yes     | Yes | Yes    | Yes   | List auctions.                             |
| /api/v3/auctions                                    | POST   | Yes     | No  | No     | No    | Create auction.                            |
| (add others as needed)                              |        |         |     |        |       |                                            |


---

## 3. Record rules (row-level) – already defined?

These limit *which rows* a role sees. Confirm they match the matrix above.


| Model                | Rule name                | Role    | Domain / intent                                                                       |
| -------------------- | ------------------------ | ------- | ------------------------------------------------------------------------------------- |
| consignment.contract | rule_consignment_manager | Manager | All rows.                                                                             |
| consignment.contract | rule_consignment_rep     | Rep     | rep_ids or create_uid.                                                                |
| consignment.contract | rule_consignment_seller  | Seller  | seller_id = partner.                                                                  |
| consignment.contract | rule_consignment_buyer   | Buyer   | buyer_id = partner.                                                                   |
| res.partner          | rule_partner_manager     | Manager | All.                                                                                  |
| res.partner          | rule_partner_rep         | Rep     | rep_ids or parent_id.rep_ids (sellers/children) OR contact_type Rep (full reps list). |
| res.partner          | rule_partner_seller      | Seller  | id = partner (own).                                                                   |
| res.partner          | rule_partner_buyer       | Buyer   | id = partner (own).                                                                   |
| sale.auction         | rule_auction_manager     | Manager | All.                                                                                  |
| sale.auction         | rule_auction_rep         | Rep     | Status = 'scheduled', 'live', 'finished', 'closed'                                    |
| sale.auction         | rule_auction_seller      | Seller  | Status = 'scheduled', 'live', 'finished', 'closed'                                    |
| sale.auction         | rule_auction_buyer       | Buyer   | Status = 'scheduled', 'live', 'finished', 'closed'                                    |


**Note:** If `rule_auction_rep`, `rule_auction_seller`, or `rule_auction_buyer` are not yet in `consignment_contract_security.xml`, add them when granting Rep/Seller/Buyer access to `sale.auction`.

---

## 4. Implementation checklist (after filling matrix)

- Add ir.model.access first (ACLs); record rules only apply after ACLs pass.
- Add/update rows in `security/ir.model.access.csv` for Rep (and Seller/Buyer) per Section 1.
- Add record rules for any new model/role combinations.
- Optionally restrict API by role in code (e.g. block Seller from POST /api/v3/contracts) for clarity.
- Re-test as Rep, Seller, Buyer after changes.


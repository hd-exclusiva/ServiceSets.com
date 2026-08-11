cpq.composition (het "recept" / sjabloon van een samenstelbaar product)
  ├── name, base_product_tmpl_id (optioneel: een 'omhulsel'-product)
  └── component_line_ids → cpq.composition.line

cpq.composition.line (welke producten mogen/moeten in de samenstelling)
  ├── product_tmpl_id (het te kiezen deelproduct)
  ├── min_qty, max_qty
  ├── required (bool)
  └── group_id (voor "kies 1 uit groep X")

cpq.personalization
  ├── sale_order_line_id / cpq.configuration_id
  ├── type (selection: 'logo_upload', 'box_design')
  ├── attachment_id (ir.attachment — voor logo/ontwerp bestand)
  ├── placement_notes / positie-data (bv. JSON met x/y/rotatie als je een preview-tool bouwt)
  └── design_data (JSON, voor eigen doos-ontwerp parameters)

cpq.configuration (de "instantie" — wat de klant daadwerkelijk gekozen heeft)
  ├── composition_id
  ├── line_ids (m2m naar gekozen componenten + hoeveelheden)
  ├── personalization_id
  ├── computed_dimensions (L x B x H van het samengestelde geheel)
  └── suggested_box_id → resultaat van de py3dbp-berekening



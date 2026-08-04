# Transfer notes

Use only these exact Vapi destination identifiers. Never include phone numbers
in the generated prompt.

- `champions_shop`: Champions Shop and Champions Course golf operations.
- `brian_onorato`: Brian Onorato.
- `krista_reyes`: Krista Reyes.
- `adam_gilbertsen`: Adam Gilbertsen.
- `logan_downey`: Logan Downey.
- `draftkings_gm`: DraftKings GM.
- `brad_williams`: Brad Williams.
- `matt_williamson`: Matt Williamson.
- `stadium_shop`: Stadium Shop and Stadium Course golf operations.
- `doug_hodge`: Doug Hodge.
- `uro_vazquez`: Uro Vazquez.
- `abby_muhlenbruch`: Abby Muhlenbruch.
- `randy_waymire`: Randy Waymire.
- `brandon_reese`: Brandon Reese.
- `julie_custer`: Julie Custer.
- `aric_runge`: Aric Runge.
- `assistant_gc`: Assistant GC.
- `william_kenworthy`: William Kenworthy.
- `michelle_seman`: Michelle Seman.
- `rob_rashell`: Rob Rashell.
- `haley_martin`: Haley Martin.
- `angie_knope`: Angie Knope.
- `andrew_yoder`: Andrew Yoder.
- `craig_smith`: Craig Smith.
- `chris_mccluskie`: Chris McCluskie.
- `caddie_master`: Caddie Master and caddie-service inquiries.
- `hostess_1`: Hostess 1 and applicable host-stand assistance.
- `draftkings_bar`: DraftKings Bar.
- `isabel_batchelor`: Isabel Batchelor.
- `casey_harrell`: Casey Harrell.

For every normal transfer, follow the non-integrated reference prompt's
two-step confirmation protocol. Ask whether the caller wants the transfer, stop
and wait, and invoke `transfer_call-staging` only after an affirmative response
in a later turn.

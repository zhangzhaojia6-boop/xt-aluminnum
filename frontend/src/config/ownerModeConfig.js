export const OWNER_MODE_CONFIG = {
  inventory_keeper: {
    title: '填出入库',
    coreCardTitle: '今日进出',
    coreStepTitle: '进出',
    supplementalCardTitle: '结存复核',
    supplementalStepTitle: '结存',
    coreSections: [
      {
        title: '今日入库',
        fieldNames: [
          'storage_inbound_weight',
          'storage_inbound_area',
          'plant_to_park_inbound_weight',
          'park_to_storage_inbound_weight',
        ],
      },
      {
        title: '今日发货',
        fieldNames: [
          'shipment_weight',
          'shipment_area',
          'month_to_date_shipment_weight',
          'month_to_date_shipment_area',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '结存与备料',
        fieldNames: [
          'month_to_date_inbound_weight',
          'month_to_date_inbound_area',
          'consignment_weight',
          'finished_inventory_weight',
          'shearing_prepared_weight',
        ],
      },
    ],
  },
  utility_manager: {
    title: '填水电气',
    coreCardTitle: '介质录入',
    coreStepTitle: '介质',
    supplementalCardTitle: '水量补录',
    supplementalStepTitle: '用水',
    coreSections: [
      {
        title: '用电',
        fieldNames: [
          'total_electricity_kwh',
          'new_plant_electricity_kwh',
          'park_electricity_kwh',
        ],
      },
      {
        title: '天然气',
        fieldNames: [
          'cast_roll_gas_m3',
          'smelting_gas_m3',
          'heating_furnace_gas_m3',
          'boiler_gas_m3',
          'total_gas_m3',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '用水',
        fieldNames: ['groundwater_ton', 'tap_water_ton'],
      },
    ],
  },
  contracts: {
    title: '填合同',
    coreCardTitle: '合同进度',
    coreStepTitle: '合同',
    supplementalCardTitle: '投料补录',
    supplementalStepTitle: '投料',
    coreSections: [
      {
        title: '当日合同',
        fieldNames: ['daily_contract_weight', 'daily_hot_roll_contract_weight'],
      },
      {
        title: '月累计与余合同',
        fieldNames: [
          'month_to_date_contract_weight',
          'month_to_date_hot_roll_contract_weight',
          'remaining_contract_weight',
          'remaining_hot_roll_contract_weight',
          'remaining_contract_delta_weight',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '投料与坯料',
        fieldNames: [
          'billet_inventory_weight',
          'daily_input_weight',
          'month_to_date_input_weight',
        ],
      },
    ],
  },
  energy_stat: {
    title: '填能耗',
    coreCardTitle: '能耗录入',
    coreStepTitle: '能耗',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '电耗与气耗', fieldNames: ['energy_kwh', 'gas_m3'] },
    ],
    supplementalSections: [],
  },
  maintenance_lead: {
    title: '报停机',
    coreCardTitle: '停机录入',
    coreStepTitle: '停机',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '停机记录', fieldNames: ['downtime_minutes', 'downtime_reason'] },
    ],
    supplementalSections: [],
  },
  hydraulic_lead: {
    title: '报油耗',
    coreCardTitle: '耗油录入',
    coreStepTitle: '耗油',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '液压油与齿轮油', fieldNames: ['hydraulic_oil_32', 'hydraulic_oil_46', 'gear_oil'] },
    ],
    supplementalSections: [],
  },
  consumable_stat: {
    title: '报辅材',
    coreCardTitle: '辅材录入',
    coreStepTitle: '辅材',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [],
    supplementalSections: [],
  },
  qc: {
    title: '填质检',
    coreCardTitle: '质检录入',
    coreStepTitle: '质检',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '质检结论', fieldNames: ['qc_grade', 'qc_notes'] },
    ],
    supplementalSections: [],
  },
  weigher: {
    title: '核重量',
    coreCardTitle: '核实重量',
    coreStepTitle: '称重',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '核实重量', fieldNames: ['verified_input_weight', 'verified_output_weight'] },
    ],
    supplementalSections: [],
  },
}

export const CONSUMABLE_SECTIONS_BY_WORKSHOP = {
  casting: [
    { title: '铸轧辅材', fieldNames: ['liquefied_gas_per_ton', 'titanium_wire_per_ton', 'steel_strip_per_ton', 'magnesium_per_ton', 'manganese_per_ton', 'iron_per_ton', 'copper_per_ton'] },
  ],
  hot_roll: [
    { title: '热轧辅材', fieldNames: ['hot_roll_emulsion_per_ton'] },
  ],
  cold_roll: [
    { title: '冷轧辅材', fieldNames: ['rolling_oil_per_ton', 'filter_agent_per_ton', 'diatomite_per_ton', 'white_earth_per_ton', 'filter_cloth_daily', 'high_temp_tape_daily', 'regen_oil_out', 'regen_oil_in'] },
  ],
  finishing: [
    { title: '精整辅材', fieldNames: ['rolling_oil_per_ton', 'd40_per_ton', 'steel_plate_per_ton', 'steel_strip_per_ton', 'steel_buckle_per_ton', 'high_temp_tape_daily'] },
  ],
}

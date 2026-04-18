from app.adapters.mes_adapter import CardInfo, CoilSnapshot, NullMesAdapter


def test_card_info_and_coil_snapshot_contract_include_phase1_clues():
    card = CardInfo(card_no='RA260001', process_route_code='MES-RA', batch_no='B-1', qr_code='QR-1')
    snapshot = CoilSnapshot(
        coil_id='coil-1',
        tracking_card_no='RA260001',
        batch_no='B-1',
        qr_code='QR-1',
    )

    assert card.batch_no == 'B-1'
    assert card.qr_code == 'QR-1'
    assert snapshot.batch_no == 'B-1'
    assert snapshot.qr_code == 'QR-1'


def test_null_mes_adapter_supports_phase1_snapshot_pull_contract():
    adapter = NullMesAdapter()

    items, cursor = adapter.list_coil_snapshots(cursor='cursor-1', updated_after=None, limit=10)

    assert items == []
    assert cursor == 'cursor-1'

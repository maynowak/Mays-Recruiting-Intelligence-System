import sys
import types
from unittest.mock import MagicMock, patch

sys.path.insert(0, "tools")
from ris_admin.cli import build_parser, cmd_doctor

def test_parser_help():
    parser = build_parser()
    assert parser.prog == "ris-admin"

def test_doctor_dry():
    # Mock boto3 Session to avoid real AWS calls
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}
    mock_session = MagicMock()
    mock_session.client.return_value = mock_sts
    mock_session_cls = MagicMock(return_value=mock_session)

    # Inject fake boto3 module
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.session = types.SimpleNamespace(Session=mock_session_cls)

    with patch.dict(sys.modules, {"boto3": fake_boto3}):
        # Need to reload module to pick up patched boto3
        import importlib
        import ris_admin.cli as cli
        importlib.reload(cli)
        args = cli.argparse.Namespace(profile="test", region="eu-central-1", environment=None, dry_run=False, output="json")
        # Patch boto3 inside module
        cli.boto3 = fake_boto3
        ret = cli.cmd_doctor(args)
        assert ret == 0

"""Exercise load_root without importing a game runtime or touching real saves."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS


def loader_namespace(tmp_path, *, invoke_error=False):
    tree = ast.parse(Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'load_root')
    calls = []
    payload = tmp_path / 'payload.bin'
    save = tmp_path / 'example.save'
    save.write_bytes(b'save')
    payload.write_bytes(b'payload')
    managed_bytes = object()
    stream = NS(Position=4)
    root = object()
    def read_all(path):
        calls.append(('native_read', path))
        return managed_bytes
    def memory_stream(data):
        assert data is managed_bytes, 'Python bytes must not cross pythonnet element by element'
        calls.append(('memory_stream', data))
        return stream
    def invoke(_target, args):
        calls.append(('invoke', args))
        if invoke_error:
            raise ValueError('bad graph')
        return root
    method = NS(Name='Deserialize', IsStatic=True, Invoke=invoke)
    def prepare():
        calls.append(('prepare',))
        payload.write_bytes(b'payload')
        return 4096, 7
    namespace = dict(PAYLOAD=payload, SAVE=save, prepare_payload=prepare,
                     System=NS(IO=NS(File=NS(ReadAllBytes=read_all), MemoryStream=memory_stream),
                               Boolean=bool, Int32=int),
                     ASM=NS(GetType=lambda name: NS(GetMethods=lambda: [method])))
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<load_root>', 'exec'), namespace)
    return namespace, calls, root, payload


def test_payload_reads_directly_into_managed_buffer(tmp_path):
    namespace, calls, root, payload = loader_namespace(tmp_path)
    assert namespace['load_root']() == (root, 4)
    assert calls[0] == ('native_read', str(payload))
    assert calls[1][0] == 'memory_stream'
    assert calls[2][0] == 'invoke'


def test_payload_refresh_precedes_managed_read(tmp_path):
    namespace, calls, root, payload = loader_namespace(tmp_path)
    payload.unlink()
    assert namespace['load_root']() == (root, 4)
    assert [c[0] for c in calls] == ['prepare', 'native_read', 'memory_stream', 'invoke']
    calls.clear()
    namespace['load_root'](refresh_payload=True)
    assert calls[0][0] == 'prepare'


def test_deserializer_failure_propagates(tmp_path):
    import pytest
    namespace, calls, _, _ = loader_namespace(tmp_path, invoke_error=True)
    with pytest.raises(ValueError, match='bad graph'):
        namespace['load_root']()
    assert [c[0] for c in calls] == ['native_read', 'memory_stream', 'invoke']

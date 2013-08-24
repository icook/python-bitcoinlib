# Distributed under the MIT/X11 software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from __future__ import absolute_import, division, print_function, unicode_literals

import unittest
import os

from binascii import unhexlify

from bitcoin.script import *

class Test_CScriptOp(unittest.TestCase):
    def test_pushdata(self):
        def T(data, expected):
            data = unhexlify(data)
            expected = unhexlify(expected)
            serialized_data = CScriptOp.encode_op_pushdata(data)
            self.assertEqual(serialized_data, expected)

        T(b'', b'00')
        T(b'00', b'0100')
        T(b'0011223344556677', b'080011223344556677')
        T(b'ff'*0x4b, b'4b' + b'ff'*0x4b)
        T(b'ff'*0x4c, b'4c4c' + b'ff'*0x4c)
        T(b'ff'*0x4c, b'4c4c' + b'ff'*0x4c)
        T(b'ff'*0xff, b'4cff' + b'ff'*0xff)
        T(b'ff'*0x100, b'4d0001' + b'ff'*0x100)
        T(b'ff'*0xffff, b'4dffff' + b'ff'*0xffff)
        T(b'ff'*0x10000, b'4e00000100' + b'ff'*0x10000)

    def test_is_singleton(self):
        self.assertTrue(OP_0 is CScriptOp(0x00))
        self.assertTrue(OP_1 is CScriptOp(0x51))
        self.assertTrue(OP_16 is CScriptOp(0x60))
        self.assertTrue(OP_CHECKSIG is CScriptOp(0xac))

        for i in range(0x0, 0x100):
            self.assertTrue(CScriptOp(i) is CScriptOp(i))


class Test_CScript(unittest.TestCase):
    def test_tokenize_roundtrip(self):
        def T(serialized_script, expected_tokens, test_roundtrip=True):
            serialized_script = unhexlify(serialized_script)
            script_obj = CScript(serialized_script)
            actual_tokens = list(script_obj)
            self.assertEqual(actual_tokens, expected_tokens)

            if test_roundtrip:
                recreated_script = CScript(actual_tokens)
                self.assertEqual(recreated_script, serialized_script)

        T(b'', [])

        # standard pushdata
        T(b'00', [b''])
        T(b'0100', [b'\x00'])
        T(b'4b' + b'ff'*0x4b, [b'\xff'*0x4b])

        # non-optimal pushdata
        T(b'4c00', [b''], False)
        T(b'4c04deadbeef', [unhexlify(b'deadbeef')], False)
        T(b'4d0000', [b''], False)
        T(b'4d0400deadbeef', [unhexlify(b'deadbeef')], False)
        T(b'4e00000000', [b''], False)
        T(b'4e04000000deadbeef', [unhexlify(b'deadbeef')], False)

        # numbers
        T(b'4f', [OP_1NEGATE])
        T(b'51', [0x1])
        T(b'52', [0x2])
        T(b'53', [0x3])
        T(b'54', [0x4])
        T(b'55', [0x5])
        T(b'56', [0x6])
        T(b'57', [0x7])
        T(b'58', [0x8])
        T(b'59', [0x9])
        T(b'5a', [0xa])
        T(b'5b', [0xb])
        T(b'5c', [0xc])
        T(b'5d', [0xd])
        T(b'5e', [0xe])
        T(b'5f', [0xf])

        # some opcodes
        T(b'9b', [OP_BOOLOR])
        T(b'9a9b', [OP_BOOLAND, OP_BOOLOR])
        T(b'ff', [OP_INVALIDOPCODE])
        T(b'fafbfcfd', [CScriptOp(0xfa), CScriptOp(0xfb), CScriptOp(0xfc), CScriptOp(0xfd)])

        # all three types
        T(b'512103e2a0e6a91fa985ce4dda7f048fca5ec8264292aed9290594321aa53d37fdea32410478d430274f8c5ec1321338151e9f27f4c676a008bdf8638d07c0b6be9ab35c71a1518063243acd4dfe96b66e3f2ec8013c8e072cd09b3834a19f81f659cc345552ae',
          [1,
           unhexlify(b'03e2a0e6a91fa985ce4dda7f048fca5ec8264292aed9290594321aa53d37fdea32'),
           unhexlify(b'0478d430274f8c5ec1321338151e9f27f4c676a008bdf8638d07c0b6be9ab35c71a1518063243acd4dfe96b66e3f2ec8013c8e072cd09b3834a19f81f659cc3455'),
           2,
           OP_CHECKMULTISIG])

    def test_invalid_scripts(self):
        def T(serialized):
            with self.assertRaises(CScriptInvalidException):
                list(CScript(unhexlify(serialized)))

        T(b'01')
        T(b'02')
        T(b'0201')
        T(b'4b')
        T(b'4b' + b'ff'*0x4a)
        T(b'4c')
        T(b'4cff' + b'ff'*0xfe)
        T(b'4d')
        T(b'4dff')
        T(b'4dffff' + b'ff'*0xfffe)
        T(b'4e')
        T(b'4effffff')
        T(b'4effffffff' + b'ff'*0xfffe) # not going to test with 4GiB-1...

    def test_equality(self):
        # Equality is on the serialized script, not the logical meaning.
        # This is important for P2SH.
        def T(serialized1, serialized2, are_equal):
            script1 = CScript(unhexlify(serialized1))
            script2 = CScript(unhexlify(serialized2))
            if are_equal:
                self.assertEqual(script1, script2)
            else:
                self.assertNotEqual(script1, script2)

        T(b'', b'', True)
        T(b'', b'00', False)
        T(b'00', b'00', True)
        T(b'00', b'01', False)
        T(b'01ff', b'01ff', True)
        T(b'fc01ff', b'01ff', False)

        # testing equality on an invalid script is legal, and evaluates based
        # on the serialization
        T(b'4e', b'4e', True)
        T(b'4e', b'4e00', False)

    def test_add(self):
        script = CScript()
        script2 = script + 1

        # + operator must create a new instance
        self.assertIsNot(script, script2)

        script = script2
        self.assertEqual(script, b'\x51')

        script += 2
        # += should not be done in place
        self.assertIsNot(script, script2)
        self.assertEqual(script, b'\x51\x52')

        script += OP_CHECKSIG
        self.assertEqual(script, b'\x51\x52\xac')

        script += b'deadbeef'
        self.assertEqual(script, b'\x51\x52\xac\x08deadbeef')

        script = CScript() + 1 + 2 + OP_CHECKSIG + b'deadbeef'
        self.assertEqual(script, b'\x51\x52\xac\x08deadbeef')

        # big number
        script = CScript() + 2**64
        self.assertEqual(script, b'\x09\x00\x00\x00\x00\x00\x00\x00\x00\x01')

        # some stuff we can't add
        with self.assertRaises(TypeError):
            script += None
        self.assertEqual(script, b'\x09\x00\x00\x00\x00\x00\x00\x00\x00\x01')

        with self.assertRaises(TypeError):
            script += [1, 2, 3]
        self.assertEqual(script, b'\x09\x00\x00\x00\x00\x00\x00\x00\x00\x01')

        with self.assertRaises(TypeError):
            script = script + None
        self.assertEqual(script, b'\x09\x00\x00\x00\x00\x00\x00\x00\x00\x01')

    def test_repr(self):
        def T(script, expected_repr):
            actual_repr = repr(script)
            self.assertEqual(actual_repr, expected_repr)

        T( CScript([]),
          'CScript([])')

        T( CScript([1]),
          'CScript([1])')

        T( CScript([1, 2, 3]),
          'CScript([1, 2, 3])')

        T( CScript([1, b'z\xc9w\xd87=\xf8u\xec\xed\xa3b)\x8e]\t\xd4\xb7+S', OP_DROP]),
          "CScript([1, b'z\\xc9w\\xd87=\\xf8u\\xec\\xed\\xa3b)\\x8e]\\t\\xd4\\xb7+S', OP_DROP])")

        T(CScript(unhexlify(b'0001ff515261ff')),
          "CScript([b'', b'\\xff', 1, 2, OP_NOP, OP_INVALIDOPCODE])")

        # truncated scripts
        T(CScript(unhexlify(b'6101')),
          "CScript([OP_NOP, b''...<ERROR: PUSHDATA(1): truncated data>])")

        T(CScript(unhexlify(b'614bff')),
          "CScript([OP_NOP, b'\\xff'...<ERROR: PUSHDATA(75): truncated data>])")

        T(CScript(unhexlify(b'614c')),
          "CScript([OP_NOP, <ERROR: PUSHDATA1: missing data length>])")

        T(CScript(unhexlify(b'614c0200')),
          "CScript([OP_NOP, b'\\x00'...<ERROR: PUSHDATA1: truncated data>])")

    def test_is_p2sh(self):
        def T(serialized, b):
            script = CScript(unhexlify(serialized))
            self.assertEqual(script.is_p2sh(), b)

        # standard P2SH
        T(b'a9146567e91196c49e1dffd09d5759f6bbc0c6d4c2e587', True)

        # NOT a P2SH txout due to the non-optimal PUSHDATA encoding
        T(b'a94c146567e91196c49e1dffd09d5759f6bbc0c6d4c2e587', False)

    def test_is_unspendable(self):
        def T(serialized, b):
            script = CScript(unhexlify(serialized))
            self.assertEqual(script.is_unspendable(), b)

        T(b'', False)
        T(b'00', False)
        T(b'006a', False)
        T(b'6a', True)
        T(b'6a6a', True)
        T(b'6a51', True)
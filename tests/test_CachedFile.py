from unittest import TestCase

from docker_compose_templer.template import CachedFile


class TestFile(TestCase):
    def test_exists(self):
        self.assertTrue(CachedFile('./vars/vars1.yml').exists())
        self.assertFalse(CachedFile('./foo').exists())

    def test_read(self):
        fp = './files/read.txt'
        f = CachedFile(fp)
        fcontent = 'foobar'
        self.assertEqual(f.read(), fcontent)
        self.assertEqual(f.cache['content'], fcontent)

        # read cached content
        self.assertEqual(f.read(), fcontent)

        # file does not exist
        self.assertRaises(FileNotFoundError, CachedFile('./foo').read)
        # not a file
        self.assertRaises(IOError, CachedFile('./vars').read)

    def test_write(self):
        # path is not a file
        self.assertRaises(OSError, CachedFile.write, '', './vars', False)
        # file already exists
        self.assertRaises(OSError, CachedFile.write, '', './files/read.txt', False)

        # write
        fp = './files/write.txt'
        import os
        if os.path.exists(fp):
            os.remove(fp)

        write_content = 'foo'
        CachedFile.write(write_content, fp, False)
        with open(fp, 'r') as f:
            self.assertEqual(f.read(), write_content)

        if os.path.exists(fp):
            os.remove(fp)

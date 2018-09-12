from unittest import TestCase
from docker_compose_templer.cli import File


class TestFile(TestCase):
    def test_exists(self):
        self.assertTrue(File('./vars/vars1.yml').exists())
        self.assertFalse(File('./foo').exists())

    def test_read(self):
        fp = './files/read.txt'
        f = File(fp)
        fcontent = 'foobar'
        self.assertEqual(f.read(), fcontent)
        self.assertEqual(f.cache['content'], fcontent)

        # read cached content
        self.assertEqual(f.read(), fcontent)

        # file does not exist
        self.assertRaises(FileNotFoundError, File('./foo').read)
        # not a file
        self.assertRaises(IOError, File('./vars').read)

    def test_write(self):
        # path is not a file
        self.assertRaises(OSError, File.write, '', './vars', False)
        # file already exists
        self.assertRaises(OSError, File.write, '', './files/read.txt', False)

        # write
        fp = './files/write.txt'
        import os
        if os.path.exists(fp):
            os.remove(fp)

        write_content = 'foo'
        File.write(write_content, fp, False)
        with open(fp, 'r') as f:
            self.assertEqual(f.read(), write_content)

        if os.path.exists(fp):
            os.remove(fp)
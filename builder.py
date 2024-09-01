#!/usr/bin/env python3

import zipfile
import struct
import subprocess
import os
import tempfile
import argparse
from typing import BinaryIO, Tuple, List
from abc import ABC, abstractmethod


VERBOSE = False

COPY_BUFFER_SIZE = 1 * 1024 * 1024  # 1 MiB


def simg_to_img(fd_in: int, fd_out: int) -> bool:
    p = subprocess.Popen(
        ['simg2img', f'/dev/fd/{fd_in}', f'/dev/fd/{fd_out}'],
        pass_fds=[fd_in, fd_out],
        stdin=subprocess.DEVNULL,
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
        text=True,
    )
    return p.wait() == 0


def sfdisk(
        fd: int,
        instructions: str,
        cylinders: int | None = None,
        heads: int | None = None,
        sectors: int | None = None,
) -> bool:
    args = ['sfdisk', '--no-reread', '--no-tell-kernel']
    if cylinders is not None:
        args += ['-C', f'{cylinders}']
    if heads is not None:
        args += ['-H', f'{heads}']
    if sectors is not None:
        args += ['-S', f'{sectors}']
    args += ['--', f'/dev/fd/{fd}']
    p = subprocess.Popen(
        args,
        pass_fds=[fd],
        stdin=subprocess.PIPE,
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
        text=True,
    )
    p.communicate(input=instructions)
    return p.wait() == 0


def mke2fs(
        fd: int,
        root: str | None = None,
        block_size: int | None = None,
        inode_size: int | None = None,
        last_mounted: str | None = None,
        label: str | None = None,
        uuid: str | None = None,
        features: str | None = None,
        extended_options: str | None = None,
        journal_options: str | None = None,
) -> bool:
    args = ['mke2fs', '-FFt', 'ext4']
    if root is not None:
        args += ['-d', root]
    if block_size is not None:
        args += ['-b', f'{block_size}']
    if inode_size is not None:
        args += ['-I', f'{inode_size}']
    if last_mounted is not None:
        args += ['-M', last_mounted]
    if label is not None:
        args += ['-L', label]
    if uuid is not None:
        args += ['-U', uuid]
    if features is not None:
        args += ['-O', features]
    if extended_options is not None:
        args += ['-E', extended_options]
    if journal_options is not None:
        args += ['-J', journal_options]
    args += ['--', f'/dev/fd/{fd}']
    p = subprocess.Popen(
        args,
        pass_fds=[fd],
        stdin=subprocess.DEVNULL,
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
        text=True,
    )
    return p.wait() == 0


def file_to_file(file_in: BinaryIO, file_out: BinaryIO, size: int | None = None) -> int:
    cur = 0
    while size is None or cur < size:
        data = file_in.read(COPY_BUFFER_SIZE if size is None else min(COPY_BUFFER_SIZE, size - cur))
        if size is None and len(data) == 0:
            break  # Done
        assert len(data) > 0
        assert file_out.write(data) == len(data)
        cur += len(data)
    return cur


def zero_to_file(file: BinaryIO, size: int) -> int:
    cur = 0
    while cur < size:
        data = b'\x00' * min(COPY_BUFFER_SIZE, size - cur)
        assert file.write(data) == len(data)
        cur += len(data)
    return cur


class SourceImage(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def write(self, file: BinaryIO, size_hint: int | None = None) -> int:
        pass


class PioneerPartInfo(SourceImage):
    def __init__(self, version: int, id_a: str, id_b: str, id_c: str):
        super().__init__()
        self.version = version
        self.id_a = id_a
        self.id_b = id_b
        self.id_c = id_c

    def generate(self):
        data = bytearray(b'\xff' * 0x200)
        data[0x0:0x48] = struct.pack(
            '<L8sL8s4s12s4s12s4s12s',
            0xA55A5AA5,
            b'\x01\x00\x00\x00\x00\x00\x00\x00',
            self.version,
            b'\x01\x00\x00\x00\x00\x00\x00\x00',
            b'\x00\x00\x00\x00',
            self.id_a.encode('ascii'),
            b'\x00\x00\x00\x00',
            self.id_b.encode('ascii'),
            b'\x00\x00\x00\x00',
            self.id_c.encode('ascii'),
        )
        return data

    def write(self, file: BinaryIO, size_hint: int | None = None) -> int:
        data = self.generate()
        assert file.write(data) == len(data)
        return len(data)


class PioneerImage(SourceImage):
    def __init__(self, file: BinaryIO, offset: int, size: int | None = None):
        super().__init__()

        self.file = file

        self.offset = offset
        assert self.offset >= 0

        if size is not None:
            self.size = size
        else:
            self.size = file.seek(0, os.SEEK_END) - offset
        assert self.size >= 0

    def write(self, file: BinaryIO, size_hint: int | None = None) -> int:
        assert self.file.seek(self.offset, os.SEEK_SET) == self.offset
        return file_to_file(self.file, file, size=self.size)


class PioneerImageCompressed(PioneerImage):
    def __init__(self, file: BinaryIO, offset: int, size: int | None = None):
        super().__init__(file, offset, size)

    def write(self, file: BinaryIO, size_hint: int | None = None) -> int:
        with tempfile.TemporaryFile(dir='.') as file_img:
            with tempfile.TemporaryFile(dir='.') as file_simg:
                super().write(file_simg)
                assert simg_to_img(file_simg.fileno(), file_img.fileno())
            return file_to_file(file_img, file)


class PioneerImageHeader(PioneerImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file, 0x0, size=0x200)


class PioneerImageContent(PioneerImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file, 0x200)


class PioneerImageContentCompressed(PioneerImageCompressed):
    def __init__(self, file: BinaryIO):
        super().__init__(file, 0x200)


class PioneerDistImage(ABC):
    def __init__(self, file: BinaryIO):
        self.file = file

    def get_header(self) -> PioneerImageHeader:
        return PioneerImageHeader(self.file)


class PioneerDistImagePJ190BOT(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContent:
        return PioneerImageContent(self.file)


class PioneerDistImagePJ190REC(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContent:
        return PioneerImageContent(self.file)


class PioneerDistImagePJ190PLT(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContentCompressed:
        return PioneerImageContentCompressed(self.file)


class PioneerDistImageSNAPSHOT(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content_1(self) -> PioneerImage:
        return PioneerImage(self.file, offset=0x200, size=0x400)

    def get_content_2(self) -> PioneerImage:
        return PioneerImage(self.file, offset=0x600)


class PioneerDistImageHIBENDIR(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContent:
        return PioneerImageContent(self.file)


class PioneerDistImagePJ190DAT(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContentCompressed:
        return PioneerImageContentCompressed(self.file)


class PioneerDistImagePJ190UPI(PioneerDistImage):
    def __init__(self, file: BinaryIO):
        super().__init__(file)

    def get_content(self) -> PioneerImageContent:
        return PioneerImageContent(self.file)


class ImageSlot(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def get_location(self) -> Tuple[int, int]:
        pass


class ImageSlotRaw(ImageSlot):
    def __init__(self, offset: int, size: int):
        super().__init__()
        self.offset = offset
        self.size = size

    def get_location(self) -> Tuple[int, int]:
        return self.offset, self.size


class ImageSlotPartitionGeneric(ImageSlot):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def get_type(self) -> str:
        pass

    @abstractmethod
    def get_location_sect(self) -> Tuple[int, int]:
        pass

    def get_location(self) -> Tuple[int, int]:
        offset_sect, size_sect = self.get_location_sect()
        return 512 * offset_sect, 512 * size_sect


class ImageSlotPartition(ImageSlotPartitionGeneric):
    def __init__(self, offset_sect: int, size_sect: int):
        super().__init__()
        assert size_sect > 0
        self.offset_sect = offset_sect
        self.size_sect = size_sect

    def get_type(self) -> str:
        return 'L'

    def get_location_sect(self) -> Tuple[int, int]:
        return self.offset_sect, self.size_sect


class ImageSlotPartitionExtended(ImageSlotPartitionGeneric):
    def __init__(self, partitions: List[ImageSlotPartition]):
        super().__init__()
        self.partitions = partitions

    def get_type(self) -> str:
        return 'Ex'

    def get_location_sect(self) -> Tuple[int, int]:
        offset_sect = min(partition.get_location_sect()[0] - 1 for partition in self.partitions)
        size_sect = max(partition.get_location_sect()[0] + partition.get_location_sect()[1] for partition in self.partitions) - offset_sect
        return offset_sect, size_sect

    def get_partitions(self) -> List[ImageSlotPartition]:
        return self.partitions


class PartitionTable():
    def __init__(
            self,
            partition_1: ImageSlotPartitionGeneric | None,
            partition_2: ImageSlotPartitionGeneric | None,
            partition_3: ImageSlotPartitionGeneric | None,
            partition_4: ImageSlotPartitionGeneric | None,
            cylinders: int | None = None,
            heads: int | None = None,
            sectors: int | None = None,
    ):
        self.partition_1 = partition_1
        self.partition_2 = partition_2
        self.partition_3 = partition_3
        self.partition_4 = partition_4
        self.cylinders = cylinders
        self.heads = heads
        self.sectors = sectors

    def generate_instructions(self) -> str:
        instructions = (
            'label: dos\n'
            'label-id: 0x00000000\n'
        )

        for label, partition in [
                ('1', self.partition_1),
                ('2', self.partition_2),
                ('3', self.partition_3),
                ('4', self.partition_4),
        ]:
            if partition is not None:
                offset_sect, size_sect = partition.get_location_sect()
                type = partition.get_type()
                instructions += f'{label}: start={offset_sect}, size={size_sect}, type={type}\n'
            if isinstance(partition, ImageSlotPartitionExtended):
                for sub_partition in partition.get_partitions():
                    offset_sect, size_sect = sub_partition.get_location_sect()
                    type = sub_partition.get_type()
                    instructions += f'start={offset_sect}, size={size_sect}, type={type}\n'

        return instructions

    def write(self, file: BinaryIO) -> None:
        instructions = self.generate_instructions()
        assert sfdisk(file.fileno(), instructions, cylinders=self.cylinders, heads=self.heads, sectors=self.sectors)


class FileSystem(SourceImage):
    def __init__(
            self,
            root: str | None = None,
            block_size: int | None = None,
            inode_size: int | None = None,
            last_mounted: str | None = None,
            label: str | None = None,
            uuid: str | None = None,
            features: str | None = None,
            extended_options: str | None = None,
            journal_options: str | None = None,
    ):
        super().__init__()
        self.root = root
        self.block_size = block_size
        self.inode_size = inode_size
        self.last_mounted = last_mounted
        self.label = label
        self.uuid = uuid
        self.features = features
        self.extended_options = extended_options
        self.journal_options = journal_options

    def write(self, file: BinaryIO, size_hint: int | None = None) -> int:
        assert size_hint is not None

        with tempfile.TemporaryFile(dir='.') as file_fs:
            zero_to_file(file_fs, size_hint)
            assert file_fs.seek(0, os.SEEK_SET) == 0
            assert mke2fs(
                file_fs.fileno(),
                root=self.root,
                block_size=self.block_size,
                inode_size=self.inode_size,
                last_mounted=self.last_mounted,
                label=self.label,
                uuid=self.uuid,
                features=self.features,
                extended_options=self.extended_options,
                journal_options=self.journal_options,
            )
            assert file_to_file(file_fs, file) == size_hint
            return size_hint


def build_image(
        path_image: str,
        part_info: PioneerPartInfo,
        path_update: str,
        path_update_pj190bot: str,
        path_update_pj190rec: str,
        path_update_pj190plt: str,
        path_update_snapshot: str,
        path_update_hibendir: str,
        path_update_pj190dat: str,
        path_update_pj190upi: str,
        path_root_extdata: str,
        path_root_cache: str,
):
    with zipfile.ZipFile(path_update) as zip:
        dist_image_pj190bot = PioneerDistImagePJ190BOT(zip.open(path_update_pj190bot))
        dist_image_pj190rec = PioneerDistImagePJ190REC(zip.open(path_update_pj190rec))
        dist_image_pj190plt = PioneerDistImagePJ190PLT(zip.open(path_update_pj190plt))
        dist_image_snapshot = PioneerDistImageSNAPSHOT(zip.open(path_update_snapshot))
        dist_image_hibendir = PioneerDistImageHIBENDIR(zip.open(path_update_hibendir))
        dist_image_pj190dat = PioneerDistImagePJ190DAT(zip.open(path_update_pj190dat))
        dist_image_pj190upi = PioneerDistImagePJ190UPI(zip.open(path_update_pj190upi))

        fs_extdata = FileSystem(
            root=path_root_extdata,
            block_size=4096,
            inode_size=256,
            last_mounted='/extdata',
            #uuid='7e4b5dc1-2fb8-4adc-8d91-48f4b0368af2',
            features='^metadata_csum,uninit_bg,^64bit,^orphan_file',
            extended_options='lazy_itable_init=0,nodiscard',
            journal_options='size=128',
        )
        fs_cache = FileSystem(
            root=path_root_cache,
            block_size=1024,
            inode_size=128,
            label='CACHE',
            #uuid='d83e2d79-c7cc-46b2-b386-c531812a64e3',
            features='^extent,^large_file,^metadata_csum,uninit_bg,^64bit,^orphan_file',
            extended_options='lazy_itable_init=0,nodiscard',
        )

        slots_pj190bot_header = [
            ImageSlotRaw(0xAF000 + 0 * 0x200, 0x200),
            ImageSlotRaw(0xAF000 + 1 * 0x200, 0x200),
        ]
        slots_pj190rec_header = [
            ImageSlotRaw(0xAF000 + 2 * 0x200, 0x200),
            ImageSlotRaw(0xAF000 + 3 * 0x200, 0x200),
        ]
        slot_pj190plt_header = ImageSlotRaw(0xAF000 + 4 * 0x200, 0x200)
        slot_part_info = ImageSlotRaw(0xAF000 + 5 * 0x200, 0x200)
        slots_snapshot_header = [
            ImageSlotRaw(0xAF000 + 6 * 0x200, 0x200),
            ImageSlotRaw(0xAF000 + 7 * 0x200, 0x200),
        ]
        slot_hibendir_header = ImageSlotRaw(0xAF000 + 8 * 0x200, 0x200)
        slot_pj190dat_header = ImageSlotRaw(0xAF000 + 9 * 0x200, 0x200)
        slot_pj190upi_header = ImageSlotRaw(0xAF000 + 10 * 0x200, 0x200)

        slot_hibendir_content = ImageSlotRaw(0x100000, 0x20000)
        slot_pj190upi_content = ImageSlotRaw(0x120000, 0x20000)
        slots_snapshot_content_1 = [
            ImageSlotRaw(0x140000, 0x400),
            ImageSlotRaw(0x140400, 0x400),
        ]
        slots_snapshot_content_2 = [
            ImageSlotRaw(0x140800, 0xFFDFC00),
            ImageSlotRaw(0x10120400, 0xFFDFC00),
        ]
        slots_pj190bot_content = [
            ImageSlotPartition(0x20100000 // 512, 0xA00000 // 512),
            ImageSlotPartition(0x20B00000 // 512, 0xA00000 // 512),
        ]
        slots_pj190rec_content = [
            ImageSlotPartition(0x21500200 // 512, 0x1DFFE00 // 512),
            ImageSlotPartition(0x23300200 // 512, 0x1DFFE00 // 512),
        ]
        slot_pj190plt_content = ImageSlotPartition(0x25100200 // 512, 0x3FFFFE00 // 512)
        slot_pj190dat_content = ImageSlotPartition(0x6D100200 // 512, 0x1FFFFE00 // 512)

        slot_fs_extdata = ImageSlotPartition(4622336, 10420224)
        slot_fs_cache = ImageSlotPartition(3311617, 262143)

        part_table = PartitionTable(
            slots_pj190bot_content[0],
            slots_pj190bot_content[1],
            ImageSlotPartitionExtended([
                slots_pj190rec_content[0],
                slots_pj190rec_content[1],
                slot_pj190plt_content,
                slot_fs_cache,
                slot_pj190dat_content,
            ]),
            slot_fs_extdata,
            #cylinders=1024,
            #heads=128,
            #sectors=16,
        )

        with open(path_image, mode='wb') as file:
            mapping: List[Tuple[ImageSlot, SourceImage]] = list({
                slots_pj190bot_header[0]:       dist_image_pj190bot.get_header(),
                slots_pj190bot_header[1]:       dist_image_pj190bot.get_header(),
                slots_pj190rec_header[0]:       dist_image_pj190rec.get_header(),
                slots_pj190rec_header[1]:       dist_image_pj190rec.get_header(),
                slot_pj190plt_header:           dist_image_pj190plt.get_header(),
                slot_part_info:                 part_info,
                slots_snapshot_header[0]:       dist_image_snapshot.get_header(),
                slots_snapshot_header[1]:       dist_image_snapshot.get_header(),
                slot_hibendir_header:           dist_image_hibendir.get_header(),
                slot_pj190dat_header:           dist_image_pj190dat.get_header(),
                slot_pj190upi_header:           dist_image_pj190upi.get_header(),

                slots_pj190bot_content[0]:      dist_image_pj190bot.get_content(),
                slots_pj190bot_content[1]:      dist_image_pj190bot.get_content(),
                slots_pj190rec_content[0]:      dist_image_pj190rec.get_content(),
                slots_pj190rec_content[1]:      dist_image_pj190rec.get_content(),
                slot_pj190plt_content:          dist_image_pj190plt.get_content(),
                slots_snapshot_content_1[0]:    dist_image_snapshot.get_content_1(),
                slots_snapshot_content_1[1]:    dist_image_snapshot.get_content_1(),
                slots_snapshot_content_2[0]:    dist_image_snapshot.get_content_2(),
                slots_snapshot_content_2[1]:    dist_image_snapshot.get_content_2(),
                slot_hibendir_content:          dist_image_hibendir.get_content(),
                slot_pj190dat_content:          dist_image_pj190dat.get_content(),
                slot_pj190upi_content:          dist_image_pj190upi.get_content(),

                slot_fs_extdata:                fs_extdata,
                slot_fs_cache:                  fs_cache,
            }.items())

            def sort_fn(item: Tuple[ImageSlot, SourceImage]) -> int:
                return item[0].get_location()[0]

            mapping.sort(key=sort_fn)

            cur = 0
            for slot, source in mapping:
                slot_offset, slot_size = slot.get_location()
                assert cur <= slot_offset
                zero_to_file(file, slot_offset - cur)
                size = source.write(file, size_hint=slot_size)
                assert size <= slot_size
                zero_to_file(file, slot_size - size)
                cur = slot_offset + slot_size

            part_table.write(file)


PLATFORMS = {
    'AVH18': {
        'part_info': PioneerPartInfo(
            0x1020000,  # Originally shipped firmware, 0x1020000 = v1.02
            'CVJ2547-E',
            'CVJ2547-E',
            'PJDZ4-1-E',
        ),
        'update_paths': {
            'BOOT': 'AVH18/BOOT/PJ180BOT.PRG',
            'RECOVERY': 'AVH18/RECOVERY/PJ180REC.PRG',
            'PLATFORM': 'AVH18/PLATFORM/PJ180PLT.PRG',
            'SNAPSHOT': 'AVH18/SNAPSHOT/SNAPSHOT_{variant}.PRG',
            'HIBENDIR': 'AVH18/HIBENDIR/HIBENDIR.PRG',
            'USERDATA': 'AVH18/USERDATA/PJ180DAT_{variant}.PRG',
            'USERAPI': 'AVH18/USERAPI/PJ180UPI.PRG',
        },
    },
    'AVIC18': {
        'part_info': PioneerPartInfo(
            0x1020000,  # Originally shipped firmware, 0x1020000 = v1.02
            'CVJ2547-E',  # TODO
            'CVJ2547-E',  # TODO
            'PJDZ4-1-E',  # TODO
        ),
        'update_paths': {
            'BOOT': 'AVIC18/BOOT/PJ180BOT.PRG',
            'RECOVERY': 'AVIC18/RECOVERY/PJ180REC.PRG',
            'PLATFORM': 'AVIC18/PLATFORM/PJ180PLT.PRG',
            'SNAPSHOT': 'AVIC18/SNAPSHOT/SNAPSHOT_{variant}.PRG',
            'HIBENDIR': 'AVIC18/HIBENDIR/HIBENDIR.PRG',
            'USERDATA': 'AVIC18/USERDATA/PJ180DAT_{variant}.PRG',
            'USERAPI': 'AVIC18/USERAPI/PJ180UPI.PRG',
        },
    },
    'AVH19': {
        'part_info': PioneerPartInfo(
            0x1000000,  # Originally shipped firmware, 0x1000000 = v1.00
            'CVJ3973-A',
            'CVJ3973-A',
            'PJDZ5-1-A',
        ),
        'update_paths': {
            'BOOT': 'AVH19/BOOT/PJ190BOT.PRG',
            'RECOVERY': 'AVH19/RECOVERY/PJ190REC.PRG',
            'PLATFORM': 'AVH19/PLATFORM/PJ190PLT.PRG',
            'SNAPSHOT': 'AVH19/SNAPSHOT/SNAPSHOT_{variant}.PRG',
            'HIBENDIR': 'AVH19/HIBENDIR/HIBENDIR.PRG',
            'USERDATA': 'AVH19/USERDATA/PJ190DAT_{variant}.PRG',
            'USERAPI': 'AVH19/USERAPI/PJ190UPI.PRG',
        },
    },
    'AVIC19': {
        'part_info': PioneerPartInfo(
            0x1000000,  # Originally shipped firmware, 0x1000000 = v1.00
            'CVJ3973-A',  # TODO
            'CVJ3973-A',  # TODO
            'PJDZ5-1-A',  # TODO
        ),
        'update_paths': {
            'BOOT': 'AVIC19/BOOT/PJ190BOT.PRG',
            'RECOVERY': 'AVIC19/RECOVERY/PJ190REC.PRG',
            'PLATFORM': 'AVIC19/PLATFORM/PJ190PLT.PRG',
            'SNAPSHOT': 'AVIC19/SNAPSHOT/SNAPSHOT_{variant}.PRG',
            'HIBENDIR': 'AVIC19/HIBENDIR/HIBENDIR.PRG',
            'USERDATA': 'AVIC19/USERDATA/PJ190DAT_{variant}.PRG',
            'USERAPI': 'AVIC19/USERAPI/PJ190UPI.PRG',
        },
    },
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Pioneer head unit firmware image builder.',
    )

    parser.add_argument(
        'path_image',
        metavar='IMAGE-PATH',
        help='Path for the resulting firmware image (.img).',
    )
    parser.add_argument(
        'platform',
        metavar='PLATFORM',
        choices=PLATFORMS.keys(),
        help='Device platform.',
    )
    parser.add_argument(
        'path_update',
        metavar='UPDATE-PATH',
        help='Path to the firmware update file (.zip).'
    )
    parser.add_argument(
        'path_root_extdata',
        metavar='EXTDATA-PATH',
        help='Path to a .tar archive for initializing the "extdata" partition.'
    )
    parser.add_argument(
        'path_root_cache',
        metavar='CACHE-PATH',
        help='Path to a .tar archive for initializing the "cache" partition.'
    )
    parser.add_argument(
        '--variant',
        type=int,
        default=1,
        help='Device variant (different hardware variants, like maybe different screens?).',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print output of executed commands.',
    )

    args = parser.parse_args()

    platform = PLATFORMS[args.platform]
    VERBOSE = args.verbose

    def platform_format(template: str):
        return template.format(
            variant=args.variant,
        )

    build_image(
        args.path_image,
        platform['part_info'],
        args.path_update,
        platform_format(platform['update_paths']['BOOT']),
        platform_format(platform['update_paths']['RECOVERY']),
        platform_format(platform['update_paths']['PLATFORM']),
        platform_format(platform['update_paths']['SNAPSHOT']),
        platform_format(platform['update_paths']['HIBENDIR']),
        platform_format(platform['update_paths']['USERDATA']),
        platform_format(platform['update_paths']['USERAPI']),
        args.path_root_extdata,
        args.path_root_cache,
    )

    print('OK')

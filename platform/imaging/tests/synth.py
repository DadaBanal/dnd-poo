"""Synthetic DICOM studies for the platform tests.

Every dataset here is invented. The pixels are drawn from formulas and a
seeded random generator. The patient does not exist (PatientName
SYNTHETIC^..., PatientID SYN-...). The UIDs are new on every run, and each
file says so in PatientIdentityRemoved and DeidentificationMethod. Nothing
is derived from a real study, so nothing here can carry PHI.

What the shapes imitate is PMC's equipment as the record lists it: cathlab
cine runs, a 16-slice CT, a 1.5 T MRI, CR plates and a DR detector,
ultrasound that arrives either uncompressed or already JPEG-compressed, and
(since M5.5) the mammography unit, the C-arms, the gamma camera, the bone
densitometer, the dental panoramic, the retinal OCT, the endoscopy systems
and the linear accelerators' portal images.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    ExplicitVRLittleEndian,
    JPEGBaseline8Bit,
    generate_uid,
)

XA = "1.2.840.10008.5.1.4.1.1.12.1"  # X-Ray Angiographic Image Storage
CT = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
MR = "1.2.840.10008.5.1.4.1.1.4"  # MR Image Storage
CR = "1.2.840.10008.5.1.4.1.1.1"  # Computed Radiography Image Storage
DX = "1.2.840.10008.5.1.4.1.1.1.1"  # Digital X-Ray Image Storage - For Presentation
US_MF = "1.2.840.10008.5.1.4.1.1.3.1"  # Ultrasound Multi-frame Image Storage
MG = "1.2.840.10008.5.1.4.1.1.1.2"  # Digital Mammography X-Ray Image Storage - For Presentation
RF = "1.2.840.10008.5.1.4.1.1.12.2"  # X-Ray Radiofluoroscopic Image Storage
NM = "1.2.840.10008.5.1.4.1.1.20"  # Nuclear Medicine Image Storage
SC = "1.2.840.10008.5.1.4.1.1.7"  # Secondary Capture Image Storage
OPT = "1.2.840.10008.5.1.4.1.1.77.1.5.4"  # Ophthalmic Tomography Image Storage
ES = "1.2.840.10008.5.1.4.1.1.77.1.1"  # VL Endoscopic Image Storage
RTIMAGE = "1.2.840.10008.5.1.4.1.1.481.1"  # RT Image Storage


@dataclass(frozen=True)
class Kind:
    key: str
    modality: str
    sop_class: str
    description: str


KINDS = {
    "xa": Kind("xa", "XA", XA, "cathlab cine run, 59 frames"),
    "ct": Kind("ct", "CT", CT, "CT series, signed 16-bit"),
    "mr": Kind("mr", "MR", MR, "MR series, 12-bit"),
    "cr": Kind("cr", "CR", CR, "CR chest plate, 12-bit"),
    "dx": Kind("dx", "DX", DX, "DR chest, 14-bit"),
    "us": Kind("us", "US", US_MF, "ultrasound cine, uncompressed RGB"),
    "us-jpeg": Kind("us-jpeg", "US", US_MF, "ultrasound cine, already JPEG (lossy)"),
    # The rest of PMC's machines (README: Every machine PMC has).
    "mg": Kind("mg", "MG", MG, "mammogram, CC and MLO, 12-bit"),
    "rf": Kind("rf", "RF", RF, "C-arm fluoroscopy run, 20 frames"),
    "nm": Kind("nm", "NM", NM, "bone scan, anterior and posterior"),
    "bmd": Kind("bmd", "BMD", SC, "bone density scan, AP spine"),
    "px": Kind("px", "PX", DX, "dental panoramic, 12-bit"),
    "opt": Kind("opt", "OPT", OPT, "retinal OCT, 12 B-scans"),
    "es": Kind("es", "ES", ES, "endoscopy photographs, RGB"),
    "rt": Kind("rt", "RTIMAGE", RTIMAGE, "radiotherapy portal image"),
}


def _now() -> dt.datetime:
    # PMC's clock: the worklist tests match on today's date as a modality would.
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))


def _grid(rows: int, cols: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.mgrid[0:rows, 0:cols].astype(np.float32)
    return (x - cols / 2) / (cols / 2), (y - rows / 2) / (rows / 2)


def xa_frames(frames: int = 59, size: int = 512, seed: int = 1) -> np.ndarray:
    """A contrast run: vessels fill from the top, then wash out."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    base = 175 - 45 * np.exp(-((x - size / 2) ** 2 + (y - size / 2) ** 2) / (2 * (size / 2.2) ** 2))
    vessels = np.zeros((size, size), np.float32)
    for _ in range(7):
        centre = rng.uniform(80, size - 80) + rng.uniform(20, 60) * np.sin(
            rng.uniform(0.004, 0.02) * y + rng.uniform(0, 2 * np.pi)
        )
        vessels = np.maximum(vessels, np.exp(-((x - centre) ** 2) / (2 * rng.uniform(2.5, 7) ** 2)))
    out = np.empty((frames, size, size), np.uint8)
    for f in range(frames):
        fill = min(1.0, f / (frames * 0.35)) * (1 - max(0.0, (f - frames * 0.7) / (frames * 0.3)))
        front = (y < size * min(1.0, 0.1 + f / (frames * 0.45))).astype(np.float32)
        img = base - 95 * fill * vessels * front + rng.normal(0, 4, (size, size))
        out[f] = np.clip(img, 0, 255).astype(np.uint8)
    return out


def ct_slices(slices: int = 40, size: int = 512, seed: int = 2) -> np.ndarray:
    """An axial chest: air, body, lungs, heart and spine, in Hounsfield units."""
    rng = np.random.default_rng(seed)
    x, y = _grid(size, size)
    out = np.empty((slices, size, size), np.int16)
    for z in range(slices):
        t = z / max(1, slices - 1)
        img = np.full((size, size), -1000.0, np.float32)
        img[(x / 0.86) ** 2 + (y / 0.64) ** 2 <= 1] = 40
        lung = 0.24 + 0.08 * np.sin(np.pi * t)
        for side in (-1, 1):
            img[((x - side * 0.36) / lung) ** 2 + ((y + 0.04) / 0.36) ** 2 <= 1] = -850
        img[((x - 0.08) / (0.16 + 0.03 * np.sin(3 * t))) ** 2 + ((y - 0.05) / 0.2) ** 2 <= 1] = 45
        img[(x / 0.08) ** 2 + ((y - 0.46) / 0.08) ** 2 <= 1] = 700
        img += rng.normal(0, 12, (size, size))
        out[z] = np.clip(img, -1024, 3071).astype(np.int16)
    return out


def mr_slices(slices: int = 20, size: int = 256, seed: int = 3) -> np.ndarray:
    """An axial head: scalp, brain and ventricles, 12-bit."""
    rng = np.random.default_rng(seed)
    x, y = _grid(size, size)
    out = np.empty((slices, size, size), np.uint16)
    for z in range(slices):
        t = z / max(1, slices - 1)
        img = np.zeros((size, size), np.float32)
        img[(x / 0.78) ** 2 + (y / 0.9) ** 2 <= 1] = 1400
        img[(x / 0.7) ** 2 + (y / 0.82) ** 2 <= 1] = 900
        v = 0.1 + 0.08 * np.sin(np.pi * t)
        for side in (-1, 1):
            img[((x - side * 0.12) / v) ** 2 + (y / 0.3) ** 2 <= 1] = 2600
        img += rng.normal(0, 25, (size, size))
        out[z] = np.clip(img, 0, 4095).astype(np.uint16)
    return out


def chest_plate(rows: int, cols: int, bits: int, seed: int) -> np.ndarray:
    """A PA chest: bright mediastinum, dark lungs, ribs as soft bands."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    top = (1 << bits) - 1
    img = 0.25 + 0.35 * np.exp(-(x**2) / 0.04)
    img += 0.25 * (np.abs(x) > 0.85)
    img += 0.06 * np.sin(18 * (y + 0.1 * x**2)) * (np.abs(x) < 0.8)
    img += rng.normal(0, 0.01, (rows, cols))
    return np.clip(img * top, 0, top).astype(np.uint16)


def us_frames(frames: int = 16, rows: int = 240, cols: int = 320, seed: int = 4) -> np.ndarray:
    """A sector of speckle with a colour-flow box, RGB."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    r = np.hypot(x, y + 1)
    theta = np.arctan2(x, y + 1)
    sector = (r < 1.9) & (np.abs(theta) < 0.6)
    out = np.zeros((frames, rows, cols, 3), np.uint8)
    for f in range(frames):
        speckle = rng.rayleigh(0.35, (rows, cols)) * (0.6 + 0.4 * np.cos(6 * r - 0.3 * f))
        grey = np.clip(speckle * 150, 0, 255) * sector
        frame = np.repeat(grey[..., None], 3, axis=2)
        box = sector & (np.abs(x) < 0.2) & (y > -0.2) & (y < 0.3)
        flow = np.sin(8 * y + 0.5 * f) > 0
        frame[box & flow] = (200, 40, 40)
        frame[box & ~flow] = (40, 60, 210)
        out[f] = frame.astype(np.uint8)
    return out


def mammogram(rows: int, cols: int, bits: int, view: str, seed: int) -> np.ndarray:
    """A breast against the chest wall at the left edge: fat, denser gland,
    fibres, the skin line, and the pectoral muscle on the MLO view."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    top = (1 << bits) - 1
    shape = ((x + 1) / 1.7) ** 2 + (y / 0.85) ** 2
    inside = shape <= 1
    img = np.full((rows, cols), 0.03, np.float32)
    tissue = 0.32 + 0.28 * np.exp(-(((x + 0.55) / 0.5) ** 2 + (y / 0.45) ** 2))
    tissue += 0.05 * np.sin(14 * y + 9 * x) * np.exp(-((y / 0.6) ** 2))
    tissue += rng.normal(0, 0.012, (rows, cols))
    img[inside] = tissue[inside]
    img[inside & (shape > 0.93)] += 0.12
    if view == "MLO":
        img[inside & (y < -0.35 - 0.8 * (x + 1))] += 0.18
    return np.clip(img * top, 0, top).astype(np.uint16)


def rf_frames(frames: int = 20, size: int = 512, seed: int = 8) -> np.ndarray:
    """A long bone under the C-arm, a nail going in a little further each frame."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    base = 118 + 22 * np.exp(-((x - size / 2) ** 2 + (y - size / 2) ** 2) / (2 * (size / 2.4) ** 2))
    axis = np.abs(x - size * 0.52 - 0.08 * (y - size / 2))
    shaft = axis < size * 0.11
    cortex = shaft & (axis > size * 0.075)
    out = np.empty((frames, size, size), np.uint8)
    for f in range(frames):
        depth = size * (0.15 + 0.7 * f / max(1, frames - 1))
        nail = (axis < size * 0.012) & (y < depth)
        img = base + 28 * shaft + 40 * cortex + 95 * nail + rng.normal(0, 5, (size, size))
        out[f] = np.clip(img, 0, 255).astype(np.uint8)
    return out


def bone_scan(rows: int = 1024, cols: int = 256, seed: int = 9) -> np.ndarray:
    """A whole-body bone scan, anterior then posterior: skull, spine, ribs,
    pelvis and long bones as counts, and one hot spot on a rib."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    body = (x / 0.55) ** 2 + (y / 0.98) ** 2 <= 1
    bone = (x / 0.28) ** 2 + ((y + 0.86) / 0.11) ** 2 <= 1  # skull
    bone |= (np.abs(x) < 0.06) & (y > -0.72) & (y < 0.1)  # spine
    for k in range(7):  # ribs
        yy = -0.6 + 0.06 * k
        bone |= (np.abs(y - yy - 0.12 * x**2) < 0.012) & (np.abs(x) < 0.34) & (np.abs(x) > 0.07)
    bone |= ((np.abs(x) - 0.18) / 0.16) ** 2 + ((y - 0.2) / 0.12) ** 2 <= 1  # pelvis
    for side in (-1, 1):  # femur, tibia, humerus
        bone |= (np.abs(x - side * 0.17 - 0.03 * (y - 0.3)) < 0.035) & (y > 0.28) & (y < 0.62)
        bone |= (np.abs(x - side * 0.19) < 0.03) & (y > 0.66) & (y < 0.97)
        bone |= (np.abs(x - side * 0.42 - 0.04 * (y + 0.3)) < 0.03) & (y > -0.6) & (y < -0.05)
    hot = ((x + 0.22) / 0.04) ** 2 + ((y + 0.42) / 0.03) ** 2 <= 1
    out = np.empty((2, rows, cols), np.uint16)
    for f in range(2):
        img = (18 + 70 * body + 420 * bone) * (1 + 0.25 * np.sin(6 * y)) + rng.poisson(30, (rows, cols))
        if f == 1:  # posterior: mirrored, the spine bright
            img = img[:, ::-1] + 260 * (bone[:, ::-1] & (np.abs(x) < 0.06))
        out[f] = np.clip(img + 2400 * hot, 0, 65535).astype(np.uint16)
    return out


def dxa_spine(rows: int = 768, cols: int = 512, seed: int = 10) -> np.ndarray:
    """A bone density scan of the lumbar spine: four vertebrae, the discs
    between them, and the analysis regions drawn over them."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    img = 30 + 55 * np.exp(-((x / 0.8) ** 2)) + rng.normal(0, 3, (rows, cols))
    for k in range(4):
        cy = -0.55 + 0.37 * k
        img += 120 * (((x / 0.2) ** 2 + ((y - cy) / 0.13) ** 2) <= 1) * (0.9 + 0.1 * k)
        img += 40 * ((np.abs(x) < 0.05) & (np.abs(y - cy) < 0.15))
        box = (np.abs(np.abs(x) - 0.26) < 0.004) & (np.abs(y - cy) < 0.17)
        box |= (np.abs(np.abs(y - cy) - 0.17) < 0.004) & (np.abs(x) < 0.26)
        img[box] = 250
    return np.clip(img, 0, 255).astype(np.uint8)


def panoramic(rows: int, cols: int, bits: int, seed: int) -> np.ndarray:
    """A dental panoramic: the arch of teeth, the mandible, the sinuses and
    the spine's shadow at both ends."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    top = (1 << bits) - 1
    img = 0.08 + 0.18 * np.exp(-((y / 0.9) ** 2))
    arch = 0.55 * x**2 - 0.1
    for row, phase in ((0.0, 0.0), (0.16, 0.4)):  # upper and lower teeth
        band = np.abs(y - arch - row) < 0.075
        teeth = np.cos(28 * x + phase) > -0.2
        img += 0.42 * band * teeth * (np.abs(x) < 0.82)
    jaw = (np.abs(y - (0.55 * x**2 + 0.28)) < 0.05) & (np.abs(x) < 0.92)
    img += 0.3 * jaw
    img += 0.16 * ((np.abs(x) > 0.86) & (y > -0.2))  # cervical spine
    for side in (-1, 1):  # sinuses
        img -= 0.06 * ((((x - side * 0.36) / 0.16) ** 2 + ((y + 0.42) / 0.14) ** 2) <= 1)
    img += rng.normal(0, 0.01, (rows, cols))
    return np.clip(img * top, 0, top).astype(np.uint16)


def oct_bscans(frames: int = 12, rows: int = 496, cols: int = 512, seed: int = 12) -> np.ndarray:
    """Retinal OCT B-scans through the macula: the layers as bright bands on a
    shallow curve, the foveal pit deepest in the middle scan."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    out = np.empty((frames, rows, cols), np.uint8)
    for f in range(frames):
        dip = 0.16 * np.exp(-(((f - frames / 2) / (frames / 4)) ** 2))
        surface = 0.12 * x**2 - 0.05 - dip * np.exp(-((x / 0.18) ** 2))
        img = 8 + rng.rayleigh(6, (rows, cols))
        for depth, bright, thick in ((0.0, 110, 0.012), (0.05, 70, 0.03), (0.1, 120, 0.014), (0.16, 60, 0.03), (0.22, 200, 0.02)):
            img += bright * np.exp(-(((y - surface - depth) / thick) ** 2))
        img += 35 * ((y > surface + 0.24) & (y < surface + 0.4)) * rng.rayleigh(0.8, (rows, cols))
        out[f] = np.clip(img, 0, 255).astype(np.uint8)
    return out


def endoscopy_photo(rows: int = 480, cols: int = 640, seed: int = 13) -> np.ndarray:
    """A photograph down the bowel: pink mucosa in folds, the dark lumen off
    centre, one bright reflection, and the scope's own vignette."""
    rng = np.random.default_rng(seed)
    x, y = _grid(rows, cols)
    r = np.hypot(x - 0.15, y + 0.1)
    folds = 0.5 + 0.5 * np.sin(9 * r - 3 * np.arctan2(y + 0.1, x - 0.15))
    light = np.clip(1.15 - 0.9 * np.exp(-((r / 0.28) ** 2)) - 0.35 * np.hypot(x, y) ** 3, 0, 1)
    base = np.stack([205 + 25 * folds, 85 + 35 * folds, 95 + 30 * folds], axis=-1) * light[..., None]
    glare = np.exp(-(((x + 0.45) / 0.05) ** 2 + ((y - 0.3) / 0.05) ** 2))
    img = base + 200 * glare[..., None] + rng.normal(0, 4, (rows, cols, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def portal_image(size: int = 512, seed: int = 14) -> np.ndarray:
    """A linear accelerator's portal image: the treatment field bright, the
    pelvis inside it, the collimator's stepped edge."""
    rng = np.random.default_rng(seed)
    x, y = _grid(size, size)
    field = (np.abs(x) < 0.62 - 0.05 * (np.floor(y * 6) % 2)) & (np.abs(y) < 0.55)
    ring = (np.abs(np.hypot(x / 0.5, (y - 0.1) / 0.32) - 1) < 0.08) & field
    heads = ((np.abs(x) - 0.33) ** 2 + (y - 0.25) ** 2 <= 0.012) & field
    img = 240 + 1300 * field + 700 * ring + 600 * heads + rng.normal(0, 20, (size, size))
    return np.clip(img, 0, 4095).astype(np.uint16)


def _jpeg(frame: np.ndarray) -> bytes:
    buf = BytesIO()
    # 4:2:2 chroma, which is what YBR_FULL_422 promises.
    Image.fromarray(frame, "RGB").save(buf, format="JPEG", quality=90, subsampling=1)
    return buf.getvalue()


class Study:
    """One synthetic study: its identity, its datasets, and their original pixels."""

    def __init__(self, kind: str, run_id: str, station_aet: str, *, accession: str | None = None,
                 study_uid: str | None = None, patient_id: str | None = None, scale: float = 1.0):
        self.kind = KINDS[kind]
        self.run_id = run_id
        self.station_aet = station_aet
        stamp = _now()
        self.date = stamp.strftime("%Y%m%d")
        self.time = stamp.strftime("%H%M%S")
        code = {"us-jpeg": "UJ"}.get(kind, kind.upper())
        self.accession = accession or f"S{run_id[:8]}{code}"[:16]
        self.patient_id = patient_id or f"SYN-{run_id}-{kind.upper()}"
        self.study_uid = study_uid or generate_uid()
        self.series_uid = generate_uid()
        self.frame_of_reference = generate_uid()
        self.datasets: list[Dataset] = []
        self.pixels: list[np.ndarray] = []
        self._build(scale)

    # ---- identity shared by every instance --------------------------------
    def _base(self, number: int) -> Dataset:
        k = self.kind
        ds = Dataset()
        ds.SpecificCharacterSet = "ISO_IR 100"
        ds.ImageType = ["ORIGINAL", "PRIMARY"]
        ds.SOPClassUID = k.sop_class
        ds.SOPInstanceUID = generate_uid()
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = ds.AcquisitionDate = self.date
        ds.StudyTime = ds.SeriesTime = ds.ContentTime = self.time
        ds.AccessionNumber = self.accession
        ds.Modality = k.modality
        ds.Manufacturer = "SYNTHETIC"
        ds.ManufacturerModelName = "platform/imaging tests"
        ds.InstitutionName = "SYNTHETIC TEST SITE"
        ds.StationName = self.station_aet[:16]
        ds.ReferringPhysicianName = ""
        ds.StudyDescription = f"SYNTHETIC {k.modality} {k.description}"
        ds.SeriesDescription = k.description
        ds.PatientName = f"SYNTHETIC^{k.key.upper().replace('-', '')}"
        ds.PatientID = self.patient_id
        ds.PatientBirthDate = ""
        ds.PatientSex = "O"
        ds.PatientIdentityRemoved = "YES"
        ds.DeidentificationMethod = "Synthetic, no real patient: platform/imaging/tests/synth.py"
        ds.StudyInstanceUID = self.study_uid
        ds.SeriesInstanceUID = self.series_uid
        ds.StudyID = "1"
        ds.SeriesNumber = 1
        ds.InstanceNumber = number
        ds.PatientOrientation = ""
        ds.BurnedInAnnotation = "NO"
        return ds

    def _finish(self, ds: Dataset, pixels: np.ndarray, *, syntax: str = ExplicitVRLittleEndian,
                pixel_data: bytes | None = None) -> None:
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = ds.SOPClassUID
        meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        meta.TransferSyntaxUID = syntax
        meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
        ds.file_meta = meta
        ds.PixelData = pixel_data if pixel_data is not None else pixels.tobytes()
        # pydicom settles the pixel element's VR and length form when it
        # writes a file, but not when pynetdicom sends the dataset: say them.
        if pixel_data is not None:
            ds["PixelData"].VR = "OB"
            ds["PixelData"].is_undefined_length = True
        else:
            ds["PixelData"].VR = "OW" if ds.BitsAllocated > 8 else "OB"
        self.datasets.append(ds)
        self.pixels.append(pixels)

    @staticmethod
    def _mono(ds: Dataset, rows: int, cols: int, bits: int, signed: bool = False) -> None:
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows, ds.Columns = rows, cols
        ds.BitsAllocated = 8 if bits <= 8 else 16
        ds.BitsStored = bits
        ds.HighBit = bits - 1
        ds.PixelRepresentation = 1 if signed else 0

    # ---- the modalities ---------------------------------------------------
    def _build(self, scale: float) -> None:
        getattr(self, "_" + self.kind.key.replace("-", "_"))(scale)

    def _xa(self, scale: float) -> None:
        frames = xa_frames(frames=max(4, round(59 * scale)))
        ds = self._base(1)
        self._mono(ds, frames.shape[1], frames.shape[2], 8)
        ds.NumberOfFrames = frames.shape[0]
        ds.FrameTime = 66.667  # 15 frames a second
        ds.CineRate = 15
        ds.FrameIncrementPointer = 0x00181063  # -> FrameTime
        ds.RadiationSetting = "GR"
        ds.KVP = 80
        ds.PositionerPrimaryAngle = 30
        ds.PositionerSecondaryAngle = 20
        ds.DistanceSourceToDetector = 1100
        self._finish(ds, frames)

    def _ct(self, scale: float) -> None:
        slices = ct_slices(slices=max(2, round(40 * scale)))
        for i, img in enumerate(slices, start=1):
            ds = self._base(i)
            self._mono(ds, img.shape[0], img.shape[1], 16, signed=True)
            ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
            ds.FrameOfReferenceUID = self.frame_of_reference
            ds.PositionReferenceIndicator = ""
            ds.PixelSpacing = [0.7, 0.7]
            ds.SliceThickness = 5
            ds.ImagePositionPatient = [-179.2, -179.2, -5.0 * i]
            ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
            ds.RescaleIntercept, ds.RescaleSlope, ds.RescaleType = 0, 1, "HU"
            ds.WindowCenter, ds.WindowWidth = 40, 400
            ds.KVP = 120
            self._finish(ds, img)

    def _mr(self, scale: float) -> None:
        slices = mr_slices(slices=max(2, round(20 * scale)))
        for i, img in enumerate(slices, start=1):
            ds = self._base(i)
            self._mono(ds, img.shape[0], img.shape[1], 12)
            ds.FrameOfReferenceUID = self.frame_of_reference
            ds.PositionReferenceIndicator = ""
            ds.PixelSpacing = [0.9, 0.9]
            ds.SliceThickness = 5
            ds.ImagePositionPatient = [-115.2, -115.2, 5.0 * i]
            ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
            ds.ScanningSequence, ds.SequenceVariant, ds.ScanOptions = "SE", "NONE", ""
            ds.MRAcquisitionType = "2D"
            ds.EchoTime, ds.RepetitionTime = 90, 4000
            ds.MagneticFieldStrength = 1.5
            self._finish(ds, img)

    def _cr(self, scale: float) -> None:
        img = chest_plate(max(64, round(1280 * scale)), max(64, round(1024 * scale)), 12, seed=5)
        ds = self._base(1)
        self._mono(ds, img.shape[0], img.shape[1], 12)
        ds.BodyPartExamined, ds.ViewPosition = "CHEST", "PA"
        ds.ImagerPixelSpacing = [0.2, 0.2]
        self._finish(ds, img)

    def _dx(self, scale: float) -> None:
        side = max(64, round(1536 * scale))
        img = chest_plate(side, side, 14, seed=6)
        ds = self._base(1)
        self._mono(ds, side, side, 14)
        ds.ImageType = ["ORIGINAL", "PRIMARY", ""]
        ds.PresentationIntentType = "FOR PRESENTATION"
        ds.BodyPartExamined, ds.ViewPosition = "CHEST", "AP"
        ds.ImagerPixelSpacing = [0.14, 0.14]
        ds.PixelIntensityRelationship, ds.PixelIntensityRelationshipSign = "LOG", 1
        ds.RescaleIntercept, ds.RescaleSlope, ds.RescaleType = 0, 1, "US"
        ds.DetectorType = "SCINTILLATOR"
        ds.LossyImageCompression = "00"
        self._finish(ds, img)

    def _us_common(self, ds: Dataset, frames: np.ndarray) -> None:
        ds.SamplesPerPixel = 3
        ds.Rows, ds.Columns = frames.shape[1], frames.shape[2]
        ds.BitsAllocated, ds.BitsStored, ds.HighBit = 8, 8, 7
        ds.PixelRepresentation = 0
        ds.PlanarConfiguration = 0
        ds.NumberOfFrames = frames.shape[0]
        ds.FrameTime = 33.333
        ds.CineRate = 30
        ds.FrameIncrementPointer = 0x00181063

    def _us(self, scale: float) -> None:
        frames = us_frames(frames=max(2, round(16 * scale)))
        ds = self._base(1)
        self._us_common(ds, frames)
        ds.PhotometricInterpretation = "RGB"
        self._finish(ds, frames)

    def _us_jpeg(self, scale: float) -> None:
        frames = us_frames(frames=max(2, round(12 * scale)), rows=480, cols=640, seed=7)
        ds = self._base(1)
        self._us_common(ds, frames)
        ds.PhotometricInterpretation = "YBR_FULL_422"
        ds.LossyImageCompression = "01"
        ds.LossyImageCompressionMethod = "ISO_10918_1"
        encoded = [_jpeg(f) for f in frames]
        ds.LossyImageCompressionRatio = round(frames.nbytes / sum(map(len, encoded)), 2)
        self._finish(ds, frames, syntax=JPEGBaseline8Bit, pixel_data=encapsulate(encoded, has_bot=True))

    def _mg(self, scale: float) -> None:
        rows, cols = max(64, round(1280 * scale)), max(64, round(1024 * scale))
        for i, view in enumerate(("CC", "MLO"), start=1):
            img = mammogram(rows, cols, 12, view, seed=15 + i)
            ds = self._base(i)
            self._mono(ds, rows, cols, 12)
            ds.ImageType = ["ORIGINAL", "PRIMARY", ""]
            ds.PresentationIntentType = "FOR PRESENTATION"
            ds.BodyPartExamined, ds.ImageLaterality, ds.ViewPosition = "BREAST", "L", view
            ds.ImagerPixelSpacing = [0.1, 0.1]
            ds.PixelIntensityRelationship, ds.PixelIntensityRelationshipSign = "LOG", 1
            ds.RescaleIntercept, ds.RescaleSlope, ds.RescaleType = 0, 1, "US"
            ds.WindowCenter, ds.WindowWidth = 1500, 2600
            ds.DetectorType = "SCINTILLATOR"
            ds.LossyImageCompression = "00"
            self._finish(ds, img)

    def _rf(self, scale: float) -> None:
        frames = rf_frames(frames=max(2, round(20 * scale)))
        ds = self._base(1)
        self._mono(ds, frames.shape[1], frames.shape[2], 8)
        ds.NumberOfFrames = frames.shape[0]
        ds.FrameTime = 100  # 10 frames a second
        ds.CineRate = 10
        ds.FrameIncrementPointer = 0x00181063
        ds.PositionerType = "CARM"
        ds.RadiationSetting = "SC"
        ds.KVP = 70
        ds.DistanceSourceToDetector = 1000
        self._finish(ds, frames)

    def _nm(self, scale: float) -> None:
        frames = bone_scan(max(64, round(1024 * scale)), max(16, round(256 * scale)))
        ds = self._base(1)
        self._mono(ds, frames.shape[1], frames.shape[2], 16)
        ds.ImageType = ["ORIGINAL", "PRIMARY", "WHOLE BODY", "EMISSION"]
        ds.NumberOfFrames = frames.shape[0]
        ds.FrameIncrementPointer = [0x00540010, 0x00540020]  # energy window, detector
        ds.NumberOfEnergyWindows, ds.EnergyWindowVector = 1, [1, 1]
        ds.NumberOfDetectors, ds.DetectorVector = 2, [1, 2]
        ds.PixelSpacing = [2.4, 2.4]
        ds.Units = "CNTS"
        self._finish(ds, frames)

    def _bmd(self, scale: float) -> None:
        img = dxa_spine(max(64, round(768 * scale)), max(64, round(512 * scale)))
        ds = self._base(1)
        self._mono(ds, img.shape[0], img.shape[1], 8)
        ds.ImageType = ["DERIVED", "SECONDARY"]
        ds.ConversionType = "WSD"
        ds.BodyPartExamined = "LSPINE"
        self._finish(ds, img)

    def _px(self, scale: float) -> None:
        rows, cols = max(64, round(600 * scale)), max(64, round(1200 * scale))
        img = panoramic(rows, cols, 12, seed=11)
        ds = self._base(1)
        self._mono(ds, rows, cols, 12)
        ds.ImageType = ["ORIGINAL", "PRIMARY", ""]
        ds.PresentationIntentType = "FOR PRESENTATION"
        ds.BodyPartExamined = "JAW"
        ds.ImagerPixelSpacing = [0.1, 0.1]
        ds.PixelIntensityRelationship, ds.PixelIntensityRelationshipSign = "LOG", 1
        ds.RescaleIntercept, ds.RescaleSlope, ds.RescaleType = 0, 1, "US"
        ds.DetectorType = "SCINTILLATOR"
        ds.LossyImageCompression = "00"
        self._finish(ds, img)

    def _opt(self, scale: float) -> None:
        frames = oct_bscans(frames=max(2, round(12 * scale)))
        ds = self._base(1)
        self._mono(ds, frames.shape[1], frames.shape[2], 8)
        ds.NumberOfFrames = frames.shape[0]
        ds.FrameTime = 0
        ds.FrameIncrementPointer = 0x00181063
        ds.ImageLaterality = "R"
        ds.PixelSpacing = [0.0039, 0.0117]
        self._finish(ds, frames)

    def _es(self, scale: float) -> None:
        for i in (1, 2):
            img = endoscopy_photo(max(64, round(480 * scale)), max(64, round(640 * scale)), seed=12 + i)
            ds = self._base(i)
            ds.SamplesPerPixel = 3
            ds.PhotometricInterpretation = "RGB"
            ds.PlanarConfiguration = 0
            ds.Rows, ds.Columns = img.shape[0], img.shape[1]
            ds.BitsAllocated, ds.BitsStored, ds.HighBit = 8, 8, 7
            ds.PixelRepresentation = 0
            ds.ImageType = ["ORIGINAL", "PRIMARY"]
            ds.LossyImageCompression = "00"
            self._finish(ds, img)

    def _rt(self, scale: float) -> None:
        img = portal_image(max(64, round(512 * scale)))
        ds = self._base(1)
        self._mono(ds, img.shape[0], img.shape[1], 16)
        ds.ImageType = ["ORIGINAL", "PRIMARY", "PORTAL"]
        ds.RTImageLabel = "AP portal"
        ds.RTImagePlane = "NORMAL"
        ds.RTImagePosition = [-127.5, 127.5]
        ds.ImagePlanePixelSpacing = [0.5, 0.5]
        ds.RadiationMachineName = "SYNTHETIC LINAC"
        ds.RadiationMachineSAD = 1000
        ds.RTImageSID = 1500
        ds.GantryAngle = ds.BeamLimitingDeviceAngle = ds.PatientSupportAngle = 0
        ds.PrimaryDosimeterUnit = "MU"
        ds.ReportedValuesOrigin = "ACTUAL"
        self._finish(ds, img)

    # ---- facts the tests compare against ---------------------------------
    @property
    def instance_uids(self) -> list[str]:
        return [str(ds.SOPInstanceUID) for ds in self.datasets]

    @property
    def raw_pixel_bytes(self) -> int:
        return sum(p.nbytes for p in self.pixels)

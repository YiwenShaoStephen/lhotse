from typing import Iterable, Optional

import torch

from lhotse import validate
from lhotse.augmentation import AugmentFn
from lhotse.cut import CutSet
from lhotse.dataset.collation import collate_audio, collate_features, collate_matrices
from lhotse.features import FeatureExtractor


class UnsupervisedDataset(torch.utils.data.Dataset):
    """
    Dataset that contains no supervision - it only provides the features extracted from recordings.

    .. code-block::

        {
            'features': (B x T x F) tensor
            'features_lens': (B, ) tensor
        }
    """

    def __init__(self, cuts: CutSet) -> None:
        super().__init__()
        self.cuts = cuts
        self._validate()

    def __getitem__(self, cut_ids: Iterable[str]) -> torch.Tensor:
        cuts = self.cuts.subset(cut_ids=cut_ids)
        features, features_lens = collate_features(cuts)
        return {
            'features': features,
            'features_lens': features_lens,
        }

    def __len__(self):
        return len(self.cuts)

    def _validate(self) -> None:
        validate(self.cuts)
        assert all(cut.has_features for cut in self.cuts)


class UnsupervisedWaveformDataset(UnsupervisedDataset):
    """
    A variant of UnsupervisedDataset that provides waveform samples instead of features.
    The output is a tensor of shape (C, T), with C being the number of channels and T the number of audio samples.
    In this implemenation, there will always be a single channel.

    Returns:

    .. code-block::

        {
            'audio': (B x NumSamples) float tensor
            'audio_lens': (B, ) int tensor
        }
    """

    def __getitem__(self, cut_ids: Iterable[str]) -> torch.Tensor:
        cuts = self.cuts.subset(cut_ids=cut_ids)
        audio, audio_lens = collate_audio(cuts)
        return {
            'audio': audio,
            'audio_lens': audio_lens,
        }

    def _validate(self) -> None:
        validate(self.cuts)
        assert all(cut.has_recording for cut in self.cuts)


class DynamicUnsupervisedDataset(UnsupervisedDataset):
    """
    An example dataset that shows how to use on-the-fly feature extraction in Lhotse.
    It accepts two additional inputs - a FeatureExtractor and an optional WavAugmenter for time-domain data augmentation..
    The output is approximately the same as that of the ``UnsupervisedDataset`` -
    there might be slight differences for ``MixedCut``s, because this dataset mixes them in the time domain,
    and ``UnsupervisedDataset`` does that in the feature domain.
    Cuts that are not mixed will yield identical results in both dataset classes.
    """

    def __init__(
            self,
            feature_extractor: FeatureExtractor,
            cuts: CutSet,
            augment_fn: Optional[AugmentFn] = None,
    ):
        super().__init__(cuts)
        self.feature_extractor = feature_extractor
        self.augment_fn = augment_fn

    def __getitem__(self, cut_ids: Iterable[str]) -> torch.Tensor:
        cuts = self.cuts.subset(cut_ids=cut_ids)
        features = collate_matrices(
            cut.compute_features(
                extractor=self.feature_extractor,
                augment_fn=self.augment_fn,
            ) for cut in cuts
        )
        return features

    def _validate(self):
        validate(self.cuts)
        assert all(cut.has_recording for cut in self.cuts)

"""Transition effects between scenes.

Placeholder module -- for now, all scenes are joined with a simple hard
cut.  Future enhancements will add crossfade, dip-to-black, wipe, etc.
"""

import logging

logger = logging.getLogger(__name__)


def apply_transition(
    clip_a: str,
    clip_b: str,
    output_path: str,
    transition_type: str = "cut",
    duration: float = 0.5,
) -> str:
    """Apply a transition effect between two clips.

    Parameters
    ----------
    clip_a : str
        Path to the outgoing clip.
    clip_b : str
        Path to the incoming clip.
    output_path : str
        Destination for the clip with the transition applied.
    transition_type : str
        Type of transition.  Currently only ``"cut"`` is implemented.
    duration : float
        Duration of the transition in seconds (unused for ``"cut"``).

    Returns
    -------
    str
        Path to the output clip with the transition applied.
    """
    if transition_type == "cut":
        # No processing needed -- the concat demuxer handles hard cuts.
        logger.debug("Using hard cut between clips (no transition processing)")
        return clip_b

    # TODO: Implement crossfade transition
    # FFmpeg xfade filter:
    #   -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=<t>[v]"
    #
    # TODO: Implement dip-to-black transition
    # TODO: Implement wipe transition

    logger.warning(
        "Transition type '%s' not implemented, falling back to cut",
        transition_type,
    )
    return clip_b

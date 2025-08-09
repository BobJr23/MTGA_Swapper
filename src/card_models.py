# Card data models and utilities for MTGA Swapper
# Contains card representation classes and card-related utility functions

from typing import Tuple, List


class MTGACard:
    """
    Represents a Magic: The Gathering Arena card with its metadata.

    Attributes:
        name: The card's display name
        set_code: The expansion/set code (e.g., 'AFR', 'KHM')
        art_type: Type of artwork (1 for normal cards, others for special variants)
        grp_id: Group ID used for card identification in MTGA
        art_id: Specific artwork ID for the card
    """

    def __init__(
        self, name: str, set_code: str, art_type: str, grp_id: str, art_id: str
    ) -> None:
        self.name = name
        self.set_code = set_code
        self.art_type = art_type
        self.grp_id = grp_id
        self.art_id = art_id
        self.alternates = []
        self.image = None

    def __str__(self) -> str:
        return self.name


def format_card_display(card_tuple: Tuple[str, str, str, str, str]) -> str:
    """
    Format a card tuple into a readable string for display in the GUI.

    Args:
        card_tuple: Tuple containing (name, set_code, art_type, grp_id, art_id)

    Returns:
        Formatted string with fixed-width columns for alignment
    """
    name, set_code, art_type, grp_id, art_id = card_tuple
    return f"{name:<30} {set_code:<10} {art_type:<9} {grp_id:<8} {art_id:<8}"


def sort_cards_by_attribute(cards: List[str], sort_key: str) -> List[str]:
    """
    Sort a list of formatted card strings by the specified attribute.

    Args:
        cards: List of formatted card strings
        sort_key: Attribute to sort by ('Name', 'Set', 'ArtType', 'GrpID', 'ArtID')

    Returns:
        Sorted list of card strings
    """
    attribute_index_map = {"Name": 0, "Set": 1, "ArtType": 2, "GrpID": 3, "ArtID": 4}
    return sorted(cards, key=lambda x: x.split()[attribute_index_map[sort_key]])

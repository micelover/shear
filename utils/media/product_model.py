from dataclasses import dataclass, field




@dataclass
class ProductItem:
    title: str
    simple_title: str
    price: str
    asin: str
    url: str
    affiliate_link: str

    script: str = field(default=None, repr=False)

    # audio_path: str = None
    # subtitles_path: str = None

    # images: List[str] = field(default_factory=list)
    # videos: Dict[str, str] = field(default_factory=dict)



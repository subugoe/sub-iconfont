# SUB Icon Font

Designed by Henrik Cederblad, [Cederblad Design](http://cederbladdesign.com).

## About

This icon font contains UI symbols for various types of media and information sources. It was commissioned in 2013 by [SUB Göttingen](http://www.sub.uni-goettingen.de) | Georg-August-Universität
Niedersächsische Staats- und Universitätsbibliothek.

## Package Contents

- ##### SUB Icon Font/

    A folder that contains the final product:

    - Icon font in standard formats (**eot**, **woff**, **svg**, **ttf**)
    - **Demo** example showing the icon font used on a web page

- ##### Icons & Guidelines.pdf

    Documenting the process of creating and using the icon font:

    - **Symbol sheet** showing the icons in overview
    - **Design Principles** in effect during original design and useful should the set be extended with new icons
    - Notes and guidelines for proper end-use

- ##### Character-Map.md

    Reference for implementation:

    - Unicode values and CSS classes

- ##### License.txt

- ##### ReadMe.md


## Usage

There are multiple ways to implement icon fonts on a web page. You may take a look at the included demo inside **SUB Icon Font/** and examine the source code for an example that shows the icon font implemented on a web page. (However this example does not combine background/foreground layers, see *Layers* below.)

### Character mapping

The glyphs are mapped to the Private Use Area ([PUA](http://en.wikipedia.org/wiki/Private_Use_Area)) of Unicode. Using PUA for character mapping is considered best practice since these characters are most likely to be ignored by screen readers. See **Character-Map.md** to find out which code is assigned to which icon.

### Layers

This icon font is designed to use two graphic layers per symbol – a background layer and a foreground layer – which should be positioned, one on top of the other, with CSS. It doesn't matter which one is on top since their graphics do not overlap.

### Colors

The color/luminosity of background layers should always be darker than the foreground layers, otherwise the icons won't appear as designed.

## License

Licensed under the MIT License.
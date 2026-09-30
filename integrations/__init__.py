"""HADES integration modules, with generated package roots allowed to overlay."""

from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)

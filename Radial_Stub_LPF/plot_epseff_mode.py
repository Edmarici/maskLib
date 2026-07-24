#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mandatory mode-verification field plot (per the Rev 9 handoff): E-field
magnitude on PortSheet1 (P1's own port cross-section), from the already-
solved extract_epseff_w70 project's LastAdaptive 3D field solution -
visual confirmation that the field genuinely concentrates around the
70um strip (the P1 mode 1 result identified numerically this session:
eps_eff=5.82 at 6GHz) rather than being a spurious bulk-cavity mode.

Connects to the EXISTING solved project (no rebuild/re-solve) - run via
the same pyaedt/.AnE environment, from this file's own directory:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe plot_epseff_mode.py
"""
import os

from pyaedt import Hfss

hfss = Hfss(project='extract_epseff_w70', design='eps_eff_extraction',
            new_desktop=False, close_on_exit=False)

out_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
os.makedirs(out_dir, exist_ok=True)
export_path = os.path.join(out_dir, 'epseff_w70_mode_field.jpg')

plot = hfss.post.plot_field(
    quantity='Mag_E',
    assignment=['PortSheet1'],
    plot_type='Surface',
    setup='EpsEffSetup : LastAdaptive',
    intrinsics={'Freq': '6GHz'},
    view='yz',  # port sheet lies in the Y-Z plane (axis=X model) - face it head-on
    show=False,
    export_path=export_path,
    image_format='jpg',
    plot_label='E field magnitude on port 1 cross-section (LastAdaptive, 6GHz)',
)
print('plot_field() returned: %r' % plot)

# show=False constructs the ModelPlotter without rendering/saving it -
# export explicitly.
if not os.path.exists(export_path):
    print('export_path not written by plot_field() itself - calling .plot() explicitly')
    plot.show = False
    plot.plot(export_path)

print('Expected export path: %s' % export_path)
print('File exists: %s' % os.path.exists(export_path))

hfss.release_desktop(close_projects=False, close_desktop=False)
print('done')

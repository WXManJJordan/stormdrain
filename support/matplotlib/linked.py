from collections import defaultdict

from stormdrain.bounds import Bounds
from stormdrain.pubsub import get_exchange
from mplevents import MPLaxesManager



class LinkedPanels(object):
    """ Helper class to manage updates of linked axes.
    
        Given a set of axes instances and associated names
        ax_specs = {ax1:(xname, yname), ax2:(xname2, yname2), ...}
        this class figures out which axes are linked, and ensures that their
        limits are kept in sync with each other. 
        
        This object also maintains a bounds object that strictly refers to the
        coordinates named in the ax_specs
        
        This solves the problem where time might be on one vertical axis and
        on another horizontal axis.
        
        This class is figure-agnostic, so it can handle a set of axes linked across figures.
    """

    # margin_defaults = {
    #         'xy':(0.1, 0.1, 0.7, 0.4),
    #         'xz':(0.1, 0.5, 0.7, 0.15),
    #         'zy':(0.8, 0.1, 0.15, 0.4),
    #         'tz':(0.1, 0.8, 0.85, 0.15),
    #         # 't': (0.1, 0.85, 0.8, 0.1),
    #         }        
    #     
    def __init__(self, ax_specs):
        # self.figure = figure
        # self.panels = {}
        self._D = 2 # dimension of the axes
        self._setup_events()
        
        self.axes_managers = {}
        self.bounds = Bounds()
        self.ax_specs = ax_specs
        
        self.ax_coords = defaultdict(set)
        for ax, names in self.ax_specs.iteritems():
            assert len(names) == self._D
            for d in range(self._D):
                self.ax_coords[names[d]].add(ax)
                self.axes_managers[names] = MPLaxesManager(ax) 
        
    def _setup_events(self):
        self.interaction_xchg = get_exchange('MPL_interaction_complete')
        self.interaction_xchg.attach(self)
        self.bounds_updated_xchg = get_exchange('SD_bounds_updated') 

    def reset_axes_events(self):
        for mgr in self.axes_managers.values():
            mgr.events.reset()
            
    def bounds_updated(self):
        self.bounds_updated_xchg.send(self.bounds)

    def send(self, ax_mgr):
        """ MPL_interaction_complete messages are sent here """
        bounds = self.bounds
        # x_var, y_var = ax_mgr.coordinate_names['x'], ax_mgr.coordinate_names['y']
        axes = ax_mgr.axes
        x_var, y_var = self.ax_specs[axes]
        
        # Figure out if the axis limits have changed, and set any new bounds
        new_limits = axes.axis(emit=False)    # emit = False prevents infinite recursion    
        old_x, old_y = getattr(bounds, x_var), getattr(bounds, y_var)
        new_x, new_y = new_limits[0:2], new_limits[2:4]
        
        # Update all axis limits for all axes whose coordinates match those of the changed
        # axes
        axes_to_update = set()
        axes_to_update.update(self.ax_coords[x_var])
        axes_to_update.update(self.ax_coords[y_var])
                
        # # Handle special case of the z axis that's part of the zy axes,
        # # which isn't shared with any other axis
        # if ax_mgr is self.axes_managers['zy']:
        #     # Update one of the shared Z axes since zy changed
        #     self.axes_managers['tz'].axes.set_ylim(new_x)
        #     self.reset_axes_events()
        #     # axes.figure.canvas.draw()
        # if (ax_mgr is self.axes_managers['tz']) | (ax_mgr is self.axes_managers['xz']):
        #     # One of the shared axes changed, so update zy
        #     self.axes_managers['zy'].axes.set_xlim(new_y)
        #     self.reset_axes_events()
        #     # axes.figure.canvas.draw()        

        if (new_x != old_x) | (new_y != old_y):
            setattr(bounds, x_var, new_x)
            setattr(bounds, y_var, new_y)
            for ax in axes_to_update:
                these_coords = self.ax_specs[ax]
                ax.set_xlim(getattr(bounds, these_coords[0]))
                ax.set_ylim(getattr(bounds, these_coords[1]))
            
            self.bounds_updated()
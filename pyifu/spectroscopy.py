#! /usr/bin/env python
# -*- coding: utf-8 -*-
import warnings
import numpy as np
try:
    from astropy.io import fits as pf
except ImportError:
    warnings.warn("You do not have astropy, you should. Using pyfits instead of astropy.io.fits")
    import pyfits as pf
    
from propobject import BaseObject



__all__ = ["load_cube","load_spectrum"]

def load_cube(filename,**kwargs):
    """ Load a Cube from the given filename 
    
    Returns
    -------
    Cube
    """
    return Cube(filename, **kwargs)

def load_spectrum(filename,**kwargs):
    """ Load a Spectrum from the given filename 
    
    Returns
    -------
    Spectrum
    """
    return Spectrum(filename, **kwargs)


def synthesize_photometry(lbda, flux, filter_lbda, filter_trans,
                          normed=True):
    """ Get Photometry from the given spectral information through the given filter.

    This function converts the flux into photons since the transmission provides the
    fraction of photons that goes though.


    Parameters
    -----------
    lbda, flux: [array]
        Wavelength and flux of the spectrum from which you want to synthetize photometry
        
    filter_lbda, filter_trans: [array]
        Wavelength and transmission of the filter.

    normed: [bool] -optional-
        Shall the fitler transmission be normalized?

    Returns
    -------
    Float (photometric point)
    """
    # ---------
    # The Tool
    def integrate_photons(lbda, flux, step, flbda, fthroughput):
        """ """
        filter_interp = np.interp(lbda, flbda, fthroughput)
        dphotons = (filter_interp * flux) * lbda * 5.006909561e7
        return np.trapz(dphotons,lbda) if step is None else np.sum(dphotons*step)
    
    # ---------
    # The Code
    normband = 1. if not normed else \
      integrate_photons(lbda,np.ones(len(lbda)),None,filter_lbda,filter_trans)
      
    return integrate_photons(lbda,flux,None,filter_lbda,filter_throughput)/normband



##########################
#                        #
# Low-Level SpecSource   #
#                        #
##########################
class SpecSource( BaseObject ):
    """ Virtual Object that contains the similaties between Spectrum and Cube. """
    
    PROPERTIES         = ["rawdata","variance","lbda","header"]
    SIDE_PROPERTIES    = ["filename","fits","header"]
    DERIVED_PROPERTIES = ["data","spec_prop"]
    
    def __init__(self,filename,
                 dataindex=0,
                 varianceindex=1,
                 headerindex=None):
        """ Initializes the object
        
        Parameters
        ----------
        filename: [string/None]  
            The name of the fits file containing the spectroscopic object. 
            You can set None to create an incomplet object. 
            Run create later on to have access to its full functionality.

        dataindex: [int]         
           Index of the hdu-table where the data are
           registered. If you do not know leave 0, 
           for some cases (like MUSE) uses 1.

        varianceindex: [int]     
            Index of the hdu-table where the variance
            are registered. If you do not know leave 1.

        headerindex: [int/None] 
            Index of the hdu-table where the header you want to use it.
            The default header is the one contained in the dataindex 
            hdu table.

        Returns
        -------
        Void
        """
        self.__build__()
        if filename is not None:
            self.load(filename,dataindex=dataindex,
                      varianceindex=varianceindex,
                      headerindex=headerindex)

    def __build__(self):
        """ Low Level method that builds the _build_properties
        It for instance contains the information about Header keywords
        """
        super(SpecSource, self).__build__()
        self._build_properties= dict(
                stepkey   = "CDELT",
                startkey  = "CRVAL",
                lengthkey = "NAXIS")
        
    # =================== #
    #   Main Metods       #
    # =================== #
    # -------- #
    #  I/O     #
    # -------- #
    def load(self, filename, dataindex=0, varianceindex=1, headerindex=None):
        """ 

        lbda - If an hdu column of the fits file is name:
               "LBDA" or "LAMBDA" or "WAVE" or "WAVELENGTH" or "WAVELENGTHS",
               the column will the used as lbda
        
        """
        self._side_properties["filename"] = filename
        self._side_properties["fits"]     = pf.open(filename)
        
        if headerindex is None:
            headerindex = dataindex
            
        # Get the data
        data = self.fits[dataindex].data
        
        # Get the variance or the error
        if varianceindex is not None and len(self.fits)>varianceindex:
            if self.fits[varianceindex].name.upper() in ["ERR","ERROR", "ERRORS"]:
                variance = self.fits[varianceindex].data**2
            else:
                variance = self.fits[varianceindex].data
        else:
            variance = None
            
        # Get the LBDA if any
        lbda_ = [f.data for f in self.fits if f.name.upper() in ["LBDA","LAMBDA", "WAVE", "WAVELENGTH","WAVELENGTHS"]]
        lbda = None if len(lbda_)==0 else lbda_[0]

        # --- Create the object
        self.create(data=data, header=self.fits[headerindex].header,
                    variance=variance, lbda=lbda)

    def writeto(self,savefile,force=True,saveerror=False):
        raise NotImplementedError("Write method not implemented for SpecSources")

    # -------- #
    #  SETTER  #
    # -------- #
    def create(self,data,header=None,
                    variance=None,
                    lbda=None):
        """  High level setting method.

        Parameters
        ----------
        data: [array]
            The array containing the data
            
        variance: [array] -optional-
            The variance associated to the data. 
            This must have the same shape as data
           
        header: [pyfits/astropy fits header / None]
            Header associated to the fits file. It could contains
            the lbda information (step, size, start). This is needed
            if lbda is not given.

        lbda: [array] -optional-
            Provide the wavelength array associated with the data.
            This is not mendatory if the header contains this information
            (step, size and start values). 
            N.B: You can always use set_lbda() later on.

        Returns
        -------
        Void
        """
        self.set_header(header)
        self.set_data(data, variance, lbda)

    def set_data(self, data, variance=None, lbda=None):
        """ Set the spectral data 

        Parameters
        ----------
        data: [array]
            The array containing the data
        
        variance: [array] -optional-
            The variance associated to the data. 
            This must have the same shape as data
           
        lbda: [array] -optional-
            Provide the wavelength array associated with the data.
            This is not mendatory if the header contains this information
            (step, size and start values). 
            N.B: You can always use set_lbda() later on.

        Returns
        -------
        Void
        """
        # - 3d data
        self._properties["rawdata"] = np.asarray(data)
        # - Variance
        if variance is not None:
            if np.shape(variance) != np.shape(data):
                raise TypeError("variance and data do not have the same shape")
            self._properties["variance"] = np.asarray(variance)
            
        # - Wavelength
        if lbda is not None:
            self.set_lbda(self, lbda)

    def set_lbda(self, lbda):
        """ Set the wavelength associated with the data.
        
        Parameters
        ----------
        lbda: [None / array]
            The wavelength array associated to the data. 
            lbda can have several shape:

            - None: This reset the lbda entry. 
              If so, if called lbda will be extracted from the header 
              if possible. It would remain None otherwise.
                    
            - Array of constant step: the favored structure.
              If the step of the given array is constant (e.g. np.linspace array)
              then this array will be decomposed into step, size and start
              which value will feed the header. The self.lbda is then built from the 
              header.
              This then allow easy saving of the data following the 3d format.
            
            - Array with non constant step: This array will simply 
              be saved as is in self.lbda. 
                    
        Returns
        -------
        Void
        """
        if lbda is None:
            self._properties["lbda"] = None
            return
        # - unique step array?
        if len(np.unique(lbda[1:]-lbda[:-1]))==1:
            # slower and a bit convoluted but ensure class' consistency
            self._lbda_to_header_(lbda)
            self._properties["lbda"] = self._lbda_from_header_()
        else:
            self._properties["lbda"] = np.asarray(lbda)

        
    def set_header(self, header):
        """ Attach a header. 
        If the given header is None, an empty header will be attached.
        """
        if header is None:
            self._side_properties["header"] = pf.header.Header
        else:
            self._side_properties["header"] = header
            self._header_to_spec_prop_()
            
    # =================== #
    #   Properties        #
    # =================== #
    # --------- #
    #  Basics   #
    # --------- #
    @property
    def lbda(self):
        """ """
        if self._properties["lbda"] is None:
            self._properties["lbda"] = self._lbda_from_header_()
        return self._properties["lbda"]
    
    @property
    def rawdata(self):
        """ """
        return self._properties["rawdata"]

    def has_data(self):
        """ """
        return self.rawdata is not None

    @property
    def variance(self):
        """ """
        return self._properties["variance"]
    
    def has_variance(self):
        """ Tests if a variance has been set. True means yes. """
        return self.variance is not None

    # - derived
    @property
    def data(self):
        """ """
        if self._derived_properties["data"] is None:
            self._derived_properties["data"] = self.rawdata.copy() if self.has_data() else None
        return self._derived_properties["data"]
    
    @property
    def spec_prop(self):
        if self._derived_properties["spec_prop"] is None:
            self._derived_properties["spec_prop"] = {}
        return self._derived_properties["spec_prop"]

    def has_spec_setup(self):
        """ Test if the spaxels properties has been step up"""
        return len(self.spec_prop.keys())>0

    # - Side prop
    @property
    def filename(self):
        """ The filename of the spectral data (if any) """
        return self._side_properties["filename"]
    
    @property
    def fits(self):
        """ Fits file opened by astropy.io.fits (if any) """
        return self._side_properties["fits"]
    
    # ---------- #
    #  Header    #
    # ---------- #
    @property
    def header(self):
        """ """
        return self._side_properties["header"]

    def _lbda_from_header_(self):
        """ """
        if not self.has_spec_setup():
            return None
        return np.arange(self.spec_prop["lspix"]) * self.spec_prop["lstep"] + self.spec_prop["lstart"]

    def _lbda_to_header_(self, lbda):
        """ converts the lbda array into step, size and start and feed it to
        spec_prop

        Returns
        -------
        Void
        """
        self.spec_prop["lstep"]  = np.unique(lbda[1:]-lbda[:-1])[0]
        self.spec_prop["lspix"]  = len(lbda)
        self.spec_prop["lstart"] = lbda[0]
        
    # -----------
    # - internal    
    @property
    def _l_spix(self):
        if "lspix" not in self.spec_prop or self.spec_prop["lspix"] is None:
            self.spec_prop["lspix"] = np.shape(self.data)[0]
        return self.spec_prop["lspix"]

##############################
#                            #
#   Spectrum                 #
#                            #
##############################
class Spectrum( SpecSource ):
    """ """
    # ================ #
    #  Main Method     #
    # ================ #
    def writeto(self,savefile,force=True,saveerror=False):
        """ Save the Spectrum into the given `savefile`

        Parameters
        ----------
        savefile: [string]      
            Fullpath of the file where the spectrum will be saved.

        force: [bool] -optional-
            If the file already exist, shall this overwrite it ? 
            (hence erasing the former one)

        saveerror:  [bool]      
            Set this to True if you wish to record the error and not the variance
            in you first hdu-table. if False, the table will be called
            VARIANCE and have self.v; if True, the table will be called
            ERROR and have sqrt(self.v)

        Returns
        -------
        Void
        """
        hdul = []
        # -- Data saving
        hdul.append(pf.PrimaryHDU(self.data, self.header))
        
        # -- Variance saving
        if self.has_variance():
            hduVar  = pf.ImageHDU(np.sqrt(self.variance), name='ERROR') if saveerror else\
              pf.ImageHDU(self.variance, name='VARIANCE')
            hdul.append(hduVar)
            
        if self.has_spec_setup():
            hduVar.header.update('%s1'%self._build_properties["lengthkey"],self.spec_prop["lspix"])   
            hduVar.header.update('%s1'%self._build_properties["stepkey"],self.spec_prop["lstep"])
            hduVar.header.update('%s1'%self._build_properties["startkey"],self.spec_prop["lstart"])
        else:
            hdul.append(pf.ImageHDU(self.lbda, name='LBDA'))
                
        hdulist = pf.HDUList(hdul)
        hdulist.writeto(savefile,clobber=force)


    # --------- #
    #  Tools    #
    # --------- #
    def synthesize_photometry(self, filter_lbda, filter_trans, on="data"):
        """ Measure the photometry at wich one would have observed this spectra
        using the given filter.
        
        This method uses 'synthesize_photometry', which converts the flux into photons
        since the transmission provides the fraction of photons that goes though.


        Parameters
        -----------
        
        filter_lbda, filter_trans: [array]
            Wavelength and transmission of the filter.
            
        normed: [bool] -optional-
            Shall the fitler transmission be normalized?

        Returns
        -------
        Float (photometric point), Float/None (variance, only if this has a variance and on in ['data','rawdata'])
        """
        return synthesize_photometry(self.lbda, eval("self.%s"%on),
                                         filter_lbda, filter_trans),\
               synthesize_photometry(self.lbda, self.variance,
                                         filter_lbda, filter_trans) if self.has_variance() \
                                         and on in ["data","rawdata"] else None
    
    # --------- #
    #  PLOTTER  #
    # --------- #
    def show(self, toshow="data", ax=None, savefile=None, show=True, **kwargs):
        """ Display the spectrum.
        
        Parameters
        ----------
        toshow: [string] -optional-
            Variable you want to display. anything accessible as self.`toshow` that 
            has the same size as the wavelength. 
            If toshow is data or rawdata, the variance will automatically be added
            if it exists.
            Do not change this is you have a doubt.

        ax: [matplotlib.Axes] -optional-
            Provide the axes where the spectrum will be drawn.
            If None this will create a new one inside a new figure
            
        savefile: [string/None] -optional-
            Would you like to save the data? If so give the name of this
            file where the plot will be saved.
            You can provide an extention (.pdf or .png) if you don't both the
            .pdf and .png will be created.

        show: [bool] -optional-
            If you do not save the data (see savefile), shall the plot be shown?

        **kwargs goes to specplot (any matplotlib axes.plot entry will work)

        Returns
        -------
        Void
        """
        import matplotlib.pyplot as mpl
        from .tools import figout, specplot
        # - Axis definition
        if ax is None:
            fig = mpl.figure(figsize=[9,3.5])
            ax = fig.add_axes([0.10,0.15,0.5,0.75])
            ax.set_xlabel(r"Wavelength", fontsize="large")
            ax.set_ylabel(r"Flux", fontsize="large")
        else:
            fig  = ax.figure

        # - Ploting
        spec = eval("self.%s"%toshow)
        var  = self.variance if toshow in ["data", "rawdata"] and self.has_variance() else None

        ax.specplot(self.lbda, spec, var=var, **kwargs)
        # - out
        fig.figout(savefile=savefile, show=show)
        
    # ================ #
    #  Properties      #
    # ================ #
    def _header_to_spec_prop_(self):
        """ """
        self.spec_prop["lspix"]  = self.header.get('%s1'%self._build_properties["lengthkey"])
        self.spec_prop["lstep"]  = self.header.get('%s1'%self._build_properties["stepkey"])
        self.spec_prop["lstart"] = self.header.get('%s1'%self._build_properties["startkey"])

##############################
#                            #
#   Cubes                    #
#                            #
##############################
class Cube( SpecSource ):
    """
    This Class is the basic class upon which the other Cube will be based.
    In there, there is just the basic method.
    """
    # ================ #
    #  Main Method     #
    # ================ #
    def writeto(self,savefile,force=True,saveerror=False):
        """ Save the cube the given `savefile`

        Parameters
        ----------
        savefile: [string]      
            Fullpath of the file where the cube will be saved.

        force: [bool] -optional-
            If the file already exist, shall this overwrite it ? 
            (hence erasing the former one)

        saveerror:  [bool]      
            Set this to True if you wish to record the error and not the variance
            in you first hdu-table. if False, the table will be called
            VARIANCE and have self.v; if True, the table will be called
            ERROR and have sqrt(self.v)

        Returns
        -------
        Void
        """
        hdul = []
        # -- Data saving
        hdul.append(pf.PrimaryHDU(self.data, self.header))
        
        # -- Variance saving
        if self.has_variance():
            hduVar  = pf.ImageHDU(np.sqrt(self.variance), name='ERROR') if saveerror else\
              pf.ImageHDU(self.variance, name='VARIANCE')
            hdul.append(hduVar)
            
        if self.has_spec_setup():
            hduVar.header.update('%s1'%self._build_properties["lengthkey"],self.spec_prop["wspix"])
            hduVar.header.update('%s2'%self._build_properties["lengthkey"],self.spec_prop["nspix"])  
            hduVar.header.update('%s3'%self._build_properties["lengthkey"],self.spec_prop["lspix"])   
            
            hduVar.header.update('%s1'%self._build_properties["stepkey"],self.spec_prop["wstep"])
            hduVar.header.update('%s2'%self._build_properties["stepkey"],self.spec_prop["nstep"])
            hduVar.header.update('%s3'%self._build_properties["stepkey"],self.spec_prop["lstep"])
            
            hduVar.header.update('%s1'%self._build_properties["startkey"],self.spec_prop["wstart"])
            hduVar.header.update('%s2'%self._build_properties["startkey"],self.spec_prop["nstart"])
            hduVar.header.update('%s3'%self._build_properties["startkey"],self.spec_prop["lstart"])
        else:
            hdul.append(pf.ImageHDU(self.lbda, name='LBDA'))
                
        hdulist = pf.HDUList(hdul)
        hdulist.writeto(savefile,clobber=force)

    # --------- #
    #  SPAXEL   #
    # --------- #
    def get_sorted_spectra(self,lbda_range=None,
                               descending=False,
                               avoid_area=None,avoid_spaxel=None):
        """ Returns the brightness-sorted spaxel Coordinate.

        Parameters
        ----------
        lbda_range: [2D array / None] -optional-
            This enable to define a weavelength zone where the brightness
            will be defined. If None, full wavelength. if None in any upper 
            or lower bound, (i.e. [None, X]) no upper or lower restriction
            respectively.

        descending: [bool] -optional-
            True:  Brightest -> Faintest
            False: Faintest  -> Brightest
                       
        avoid_area: [3-floats/None] -optional-
            You can avoid an space of the Cube by defining here a position 
            (x,y) and a radius. avoid_area must be (x,y,r). 
            All spaxel inthere will be avoided in the spaxel sorting 
            (considered as Nan). 
            If None, nothing will be avoided this way. 

        avoid_spaxel: [N*2D-array/None] 
            You can set a list of sapxel coords [[sp1_x,sp1_y],[]...] these 
            spaxels will be avoided in the spaxel sorting (considered as Nan).
            If None, nothing will be avoided this way.
                                    
        Returns
        -------
        N*[X,Y] where N is the amount of spaxel (X,Y in imshow coords)
        """
        # ------------------- #
        # -- Input checked -- #
        # ------------------- #
        if lbda_range is None:
            lbda_range = [None,None]
            
        # - user gave a wrong input
        if len(lbda_range) != 2:
            raise ValueError("`lbda_range` must be None or a 2D array")

        if lbda_range[0] is None:
            lbda_range[0] = 0
            
        if lbda_range[1] is None:
            lbda_range[1] = 1e6

        # --------------------------- #
        # -- Lets sort the spaxels -- #
        # --------------------------- #
        sorting_flag = (self.lbda >= lbda_range[0]) & (self.lbda <= lbda_range[1])
        # -- this is the flat-list of brightness sorted spaxel
        # -- One Has to handle the nan otherwise argsort (and family) wont work
        
        sum_data    = np.sum(self.data[sorting_flag],axis=0)
        # -- If there is spaxel we do not want to considere
        avoidance_mask = np.ones(np.shape(sum_data))
        # -- Avoidance Area
        if avoid_area is not None and len(avoid_area) == 3:
            x,y,r2 = avoid_area[0],avoid_area[1],avoid_area[2]**2 # to save cpu
            for i in range(np.shape(sum_data)[0]):
                for j in range(np.shape(sum_data)[1]):
                    if ((i-x)**2 + (j-y)**2) <r2:
                        avoidance_mask[j,i] = np.NaN
                        
        # -- Avoided Spaxel
        if avoid_spaxel is not None:
            for sp in avoid_spaxel: # tested
                avoidance_mask[sp[0],sp[1]] = np.NaN

        sum_data    = sum_data*avoidance_mask
        # ------ Cleaned data
        
        flat_data   = np.concatenate(sum_data)
        flagnan     = (flat_data!=flat_data)
        argslist    = np.argsort(flat_data[-flagnan])
        
        maxrank     = np.nanmax(argslist)
        # -- Which sorting ?
        if descending:
            ranked = np.asarray([maxrank-np.argwhere(argslist==i)[0][0] for i in range(maxrank+1)])
        else:
            ranked = np.asarray([np.argwhere(argslist==i)[0][0] for i in range(maxrank+1)])
        
        # -- Fancy Insert
        nanindex = 0
        index_nan = np.argwhere(flagnan==True).T[0]
        full_rank = np.ones(len(flat_data))*np.NaN
        for i in range(len(flat_data)):
            if i in index_nan:
                nanindex += 1
            else:
                full_rank[i] = ranked[i-nanindex]
        
        # -- spaxel_1d_to_2d
        array2d = np.ones((self._w_spix,self._n_spix))
        for i in range(self._w_spix):
            for j in range(self._n_spix):
                if full_rank[j+self._w_spix*i] <0:
                    array2d[i,j] = np.NaN
                else:
                    array2d[i,j] = full_rank[j+self._w_spix*i]
                    
        return array2d

    def get_brightest_spaxels(self,nspaxel,lbda_range=None,
                                  avoid_area=None,avoid_spaxel=None):
        """ get the coordinates of the brightnest spaxel of the cube

        Parameters
        ----------
        nspaxel: [int]
            Number of spaxels you want.
        
        lbda_range: [2D array / None] -optional-
            This enable to define a weavelength zone where the brightness
            will be defined. If None, full wavelength. if None in any upper 
            or lower bound, (i.e. [None, X]) no upper or lower restriction
            respectively.
                       
        avoid_area: [3-floats/None] -optional-
            You can avoid an space of the Cube by defining here a position 
            (x,y) and a radius. avoid_area must be (x,y,r). 
            All spaxel inthere will be avoided in the spaxel sorting 
            (considered as Nan). 
            If None, nothing will be avoided this way. 

        avoid_spaxel: [N*2D-array/None] 
            You can set a list of sapxel coords [[sp1_x,sp1_y],[]...] these 
            spaxels will be avoided in the spaxel sorting (considered as Nan).
            If None, nothing will be avoided this way.

        Returns
        -------
        list of spaxel coordinates
        """
        spaxelsrank = self.get_sorted_spectra(lbda_range=lbda_range,
                                              avoid_area=avoid_area,
                                              avoid_spaxel=avoid_spaxel,
                                              descending=True)
            
        return np.asarray([np.argwhere(spaxelsrank==i)[0] for i in range(nspaxel)])
    
    def get_faintest_spaxels(self,nspaxel,lbda_range=None,
                               avoid_area=None,avoid_spaxel=None):
        """ get the coordinates of the faintest spaxel of the cube

        Parameters
        ----------
        nspaxel: [int]
            Number of spaxels you want.
        
        lbda_range: [2D array / None] -optional-
            This enable to define a weavelength zone where the brightness
            will be defined. If None, full wavelength. if None in any upper 
            or lower bound, (i.e. [None, X]) no upper or lower restriction
            respectively.
                       
        avoid_area: [3-floats/None] -optional-
            You can avoid an space of the Cube by defining here a position 
            (x,y) and a radius. avoid_area must be (x,y,r). 
            All spaxel inthere will be avoided in the spaxel sorting 
            (considered as Nan). 
            If None, nothing will be avoided this way. 

        avoid_spaxel: [N*2D-array/None] 
            You can set a list of sapxel coords [[sp1_x,sp1_y],[]...] these 
            spaxels will be avoided in the spaxel sorting (considered as Nan).
            If None, nothing will be avoided this way.

        Returns
        -------
        list of spaxel coordinates
        """
        spaxelsrank = self.get_sorted_spectra(lbda_range=lbda_range,
                                              avoid_area=avoid_area,
                                              avoid_spaxel=avoid_spaxel,
                                              descending=False)
            
        return np.asarray([np.argwhere(spaxelsrank==i)[0] for i in range(nspaxel)])

    
    # -------------- #
    #  Manipulation  #
    # -------------- #
    def remove_flux(self,flux):
        """
        = This enalble to remove the given flux to all the
          spaxels of the cube. =

        flux: [array]              The input flux that will be removed.

        = RETURNS =
        Void, affects the object (fluxes)
        """
        if len(flux) != len(self.lbda):
            raise ValueError("The given `spec` must have the size as the wavelength array")

        for w in range(self._w_spix):
            for n in range(self._n_spix):
                if (self.data.T[n,w] == 0).all():
                    continue
                self.data.T[n,w] -= flux
            
    # ================================ #
    # ==     External Tools         == #
    # ================================ #
    def show(self, toshow="data", savefile=None, ax=None, show=True,
                 show_meanspectrum=True, cmap=None,**kwargs):
        """ Display the cube.
        
        Parameters
        ----------
        toshow: [string] -optional-
            Variable you want to display. anything accessible as self.`toshow` that 
            has the same size as the wavelength. 
            If toshow is data or rawdata, the variance will automatically be added
            if it exists.
            Do not change this is you have a doubt.

        cmap: [matplotlib colormap]
            Colormap used for the wavelength integrated cube (imshow).

        show_meanspectrum: [bool] -optional-
            If True both a wavelength integrated cube (imshow) and the average spectrum 
            will be displayed. If not, only the wavelength integrated cube (imshow) will.

        ax: [matplotlib.Axes] -optional-
            Provide the axes where the spectrum and/or the wavelength integrated 
            cube  will be drawn. 
            See show_meanspectrum:
               - If True, 2 axes are requested so axspec, aximshow=ax
               - If False, 1 axes is needed, aximshow=ax 
            If None this will create a new axes inside a new figure
            
        savefile: [string/None] -optional-
            Would you like to save the data? If so give the name of this
            file where the plot will be saved.
            You can provide an extention (.pdf or .png) if you don't both the
            .pdf and .png will be created.

        show: [bool] -optional-
            If you do not save the data (see savefile), shall the plot be shown?

        **kwargs goes to matplotlib's imshow 

        Returns
        -------
        Void
        """
        import matplotlib.pyplot as mpl
        from .tools import figout, specplot
        # - Axis definition
        if ax is None:
            fig = mpl.figure(figsize= [6,5] if not show_meanspectrum else [10,3.5] )
            if show_meanspectrum:
                axspec = fig.add_axes([0.10,0.15,0.5,0.75])
                axim   = fig.add_axes([0.65,0.15,0.26,0.75])
                axspec.set_xlabel(r"Wavelength", fontsize="large")
                axspec.set_ylabel(r"Flux", fontsize="large")
            else:
                axim   = fig.add_axes([0.12,0.12,0.8,0.8])
                
        elif show_meanspectrum:
            axspec, axim = ax
            fig = axspec.figure
        else:
            axim = ax
            fig  = axim.figure

        # - Ploting
        stack = np.sum(eval("self.%s"%toshow), axis=0)
        axim.imshow(stack, origin="lower", interpolation="nearest",cmap=cmap,aspect='auto', **kwargs)
        if show_meanspectrum:
            spec = np.nanmean(np.concatenate(eval("self.%s"%toshow).T), axis=0)
            var  = np.nanmean(np.concatenate(self.variance.T), axis=0) \
              if toshow in ["data", "rawdata"] and self.has_variance() else None

            axspec.specplot(self.lbda, spec, var=var)
            axspec.text(0.03,0.95, "Mean Spectrum", transform=axspec.transAxes,
                            va="top", ha="left",
                          bbox={"facecolor":"w", "alpha":0.5,"edgecolor":"None"})
        
        # - out
        fig.figout(savefile=savefile, show=show)
        

    # =================== #
    #   Properties        #
    # =================== #
    def _header_to_spec_prop_(self):
        """ """
        self.spec_prop["wspix"]  = self.header.get('%s1'%self._build_properties["lengthkey"])
        self.spec_prop["nspix"]  = self.header.get('%s2'%self._build_properties["lengthkey"])
        self.spec_prop["lspix"]  = self.header.get('%s3'%self._build_properties["lengthkey"])
        
        self.spec_prop["wstep"]  = self.header.get('%s1'%self._build_properties["stepkey"])
        self.spec_prop["nstep"]  = self.header.get('%s2'%self._build_properties["stepkey"])
        self.spec_prop["lstep"]  = self.header.get('%s3'%self._build_properties["stepkey"])

        self.spec_prop["wstart"] = self.header.get('%s1'%self._build_properties["startkey"])
        self.spec_prop["nstart"] = self.header.get('%s2'%self._build_properties["startkey"])
        self.spec_prop["lstart"] = self.header.get('%s3'%self._build_properties["startkey"])

    # -----------
    # - internal
    @property
    def _w_spix(self):
        if "wspix" not in self.spec_prop or self.spec_prop["wspix"] is None:
            self.spec_prop["wspix"] = np.shape(self.data)[1]
        return self.spec_prop["wspix"]

    @property
    def _n_spix(self):
        if "nspix" not in self.spec_prop or self.spec_prop["nspix"] is None:
            self.spec_prop["nspix"] = np.shape(self.data)[2]
        return self.spec_prop["nspix"]
    
    

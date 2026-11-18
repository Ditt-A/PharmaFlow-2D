# Draft external-data request — not sent

Suggested recipient: the Cornerstones data authors or Dryad support
(`help@datadryad.org`). No message has been sent by this project.

Subject: Small documented MATLAB subset for Dryad 10.5061/dryad.cvdncjtb5

Dear data authors / Dryad curators,

We are assessing physical compatibility of an uncalibrated 2D disk DEM hopper
with your Cornerstones experiments. Public metadata are accessible, but our
documented README download returned HTTP 403 and the API requires an account token.
We do not want to mirror the 17.41 GB release or bypass access restrictions.

Could you provide a provider-supported or author-approved subset, **at most nine
files and 200 MB total**: the original README, a data dictionary, session/calibration
metadata, and six unmodified no-fixed-particle MATLAB flow runs (two prespecified
runs at each D/dL=3.61, 3.86 and 4.15)? Please select runs chronologically or by a
documented random rule before reviewing their outcomes, including any available
pauses that resume and the original observation endpoints. If that selection
exceeds 200 MB, please advise a smaller documented subset before transfer.

We need tracking/mass/time units, coordinate origins/signs and pixel calibration;
frame/timestamp alignment and velocity computation; ID/species definitions and
mixture fractions; particle dimensions/masses; outlet/plate/floor geometry; the
semicircular mass observation boundary; vibration/reset and recirculation timing;
the five-second clog confirmation versus stored time coverage; session/sequence
IDs; available repetitions/uncertainty; measured friction/restitution/roughness,
if known; and published checksums, version and reuse conditions.

Our current engine uses monodisperse strict 2D disks, a finite-fill wedge and a
separate 0.4-second finite-arch protocol. We will not equate these definitions,
fit friction to compensate for missing physics or claim calibration without a
matched independent validation target. Thank you for advising the proper access
route and any limitations of the requested measurements.

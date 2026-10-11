# Known issues

Tickets recorded but not yet fixed. Each says what is wrong, why, and the fix.

## run_timeseries_workflow never slices large datasets

**Found 9 October 2026, while fixing the re-scan of 0.3.32. Not security. Fixed in 0.3.34.**

**What the tool promises.** `run_timeseries_workflow`'s docstring says datasets
over 500 rows are cut to the most recent 500 before the ARIMA fit, to keep it
fast.

**What happens.** The cut is never used. In `stats_compass_mcp/tools/workflows.py`
the slice is stored with its arguments swapped:

```python
session.state.set_dataframe(temp_name, sliced)
```

`DataFrameState.set_dataframe` takes `(df, name, operation, set_active=True)`.
Passed a name where the frame belongs and no `operation`, it raises
`TypeError: ... missing 1 required positional argument: 'operation'` (checked
on core 0.1.40).

The surrounding `try` ends in `except Exception: pass`, so the error is
swallowed. `dataframe_name` is never switched to the sliced frame, and the
workflow fits ARIMA on the whole dataset. On a large frame that is the slow fit
the cut was meant to avoid, and the log never says the cut was skipped.

**Fix.**
- Store the frame with keyword arguments:
  `session.state.set_dataframe(sliced, name=temp_name, operation="timeseries_slice", set_active=False)`.
- Narrow the `except` so a failure is logged as a warning, not silenced.
- Add a test with a 600-row series that asserts the fit used 500 rows.
- Check the existing cleanup of `temp_name` still removes the sliced frame.

**What 0.3.34 does.** The fix above, tested in `tests/test_timeseries_slice.py`,
plus three things the slice needed once it actually ran:
- With a `date_column`, the cut keeps the 500 latest dates. Rows may not be in
  date order, and `tail(500)` would have kept the last 500 rows as stored.
- The slice is renumbered from 0 unless its index holds dates. Rows 100 to 599
  made statsmodels warn that forecasting from such an index will become an error.
- The slice is stored as `<name>_last500`, never over a DataFrame the user
  already has, so the forecast is named `<name>_last500_forecast` and says what
  it was fitted on. The slice itself is removed afterwards, as before.

If the slice can't be stored (the session's memory limit), a warning is logged
and the whole series is fitted.

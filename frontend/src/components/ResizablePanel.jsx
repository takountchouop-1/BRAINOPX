import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Box } from '@mui/material'

/**
 * ResizablePanel — wraps any content and adds a draggable resize handle.
 *
 * @param {Object} props
 * @param {string}  props.direction   - 'horizontal' (width) | 'vertical' (height)
 * @param {number}  props.minSize     - minimum size in px
 * @param {number}  props.maxSize     - maximum size in px
 * @param {number}  props.defaultSize - initial size in px
 * @param {string}  props.sx          - additional MUI sx props for the wrapper
 * @param {ReactNode} props.children
 */
const ResizablePanel = ({
  direction = 'horizontal',
  minSize = 200,
  maxSize = 800,
  defaultSize = null,
  sx = {},
  children,
}) => {
  const isHorizontal = direction === 'horizontal'

  // Compute initial size from the default or from the first child's offset
  const [size, setSize] = useState(defaultSize || (isHorizontal ? 420 : 500))
  const [isDragging, setIsDragging] = useState(false)
  const startPosRef = useRef(0)
  const startSizeRef = useRef(0)
  const panelRef = useRef(null)

  const handleMouseDown = useCallback(
    (e) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(true)
      startPosRef.current = isHorizontal ? e.clientX : e.clientY
      startSizeRef.current = size
      document.body.style.cursor = isHorizontal ? 'col-resize' : 'row-resize'
      document.body.style.userSelect = 'none'
    },
    [isHorizontal, size]
  )

  const handleMouseMove = useCallback(
    (e) => {
      if (!isDragging) return
      const currentPos = isHorizontal ? e.clientX : e.clientY
      const delta = currentPos - startPosRef.current
      // For horizontal resizing on the right side, dragging left = shrink
      const newSize = Math.min(maxSize, Math.max(minSize, startSizeRef.current + delta))
      setSize(newSize)
    },
    [isDragging, isHorizontal, minSize, maxSize]
  )

  const handleMouseUp = useCallback(() => {
    if (isDragging) {
      setIsDragging(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDragging])

  // Attach global listeners when dragging
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [])

  const handleStyle = {
    position: 'absolute',
    zIndex: 10,
    ...(isHorizontal
      ? {
          left: -3,
          top: 0,
          bottom: 0,
          width: 6,
          cursor: 'col-resize',
        }
      : {
          top: -3,
          left: 0,
          right: 0,
          height: 6,
          cursor: 'row-resize',
        }),
  }

  const handleVisual = {
    position: 'absolute',
    ...(isHorizontal
      ? {
          left: -1,
          top: 0,
          bottom: 0,
          width: 2,
        }
      : {
          top: -1,
          left: 0,
          right: 0,
          height: 2,
        }),
    bgcolor: isDragging ? 'primary.main' : 'transparent',
    transition: 'background-color 0.15s ease',
    borderRadius: 1,
  }

  return (
    <Box
      ref={panelRef}
      sx={{
        position: 'relative',
        ...(isHorizontal ? { width: size, flexShrink: 0 } : { height: size, flexShrink: 0 }),
        transition: isDragging ? 'none' : 'width 0.2s ease, height 0.2s ease',
        ...sx,
      }}
    >
      {/* Drag handle area */}
      <Box
        onMouseDown={handleMouseDown}
        sx={{
          ...handleStyle,
          '&:hover .resize-visual': {
            bgcolor: 'primary.main',
          },
          '&:active .resize-visual': {
            bgcolor: 'primary.dark',
          },
        }}
      >
        <Box className="resize-visual" sx={handleVisual} />
      </Box>

      {/* Content */}
      {children}
    </Box>
  )
}

export default ResizablePanel

/**
 * ResizableChatPanel — a pre-configured ResizablePanel for chatbot UIs.
 * Wraps the chat panel on the right side of the screen.
 */
export const ResizableChatPanel = ({ children, defaultSize = 420, sx = {} }) => {
  return (
    <ResizablePanel
      direction="horizontal"
      minSize={280}
      maxSize={900}
      defaultSize={defaultSize}
      sx={{ display: 'flex', flexDirection: 'column', ...sx }}
    >
      {children}
    </ResizablePanel>
  )
}

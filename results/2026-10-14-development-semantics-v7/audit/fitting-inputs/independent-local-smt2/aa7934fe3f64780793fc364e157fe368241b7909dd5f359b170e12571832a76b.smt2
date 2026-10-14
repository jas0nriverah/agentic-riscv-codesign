(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x941 (bvadd independent_opaque_0 (_ bv63 32))))
(and (distinct ?x941 ?x941) true)))
(check-sat)

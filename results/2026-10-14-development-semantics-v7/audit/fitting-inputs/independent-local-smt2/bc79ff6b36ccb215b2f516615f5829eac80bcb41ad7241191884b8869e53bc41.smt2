(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x792 (bvadd independent_opaque_0 (_ bv4294967285 32))))
(and (distinct ?x792 ?x792) true)))
(check-sat)

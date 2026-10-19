(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1257 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv4294965249 32)))))
(let ((?x625 (bvsub (bvadd independent_opaque_0 (_ bv4294965249 32)) independent_opaque_1)))
(and (distinct ?x625 ?x1257) true))))
(check-sat)

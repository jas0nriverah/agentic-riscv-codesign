(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x941 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv63 32)))))
(let ((?x289 (bvsub (bvadd independent_opaque_0 (_ bv63 32)) independent_opaque_1)))
(and (distinct ?x289 ?x941) true))))
(check-sat)

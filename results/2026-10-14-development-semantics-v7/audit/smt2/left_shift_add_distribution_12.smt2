(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x156 (bvshl y (_ bv12 32))))
(let ((?x152 (bvshl x (_ bv12 32))))
(let ((?x157 (bvadd ?x152 ?x156)))
(let ((?x19 (bvadd x y)))
(let ((?x155 (bvshl ?x19 (_ bv12 32))))
(and (distinct ?x155 ?x157) true)))))))
(check-sat)
